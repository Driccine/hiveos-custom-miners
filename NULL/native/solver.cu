// SPDX-License-Identifier: MIT
// Experimental original CUDA solver for NULL Equihash (144,5).
// No third-party miner, development fee, wallet or network code here.
#include "blake.hpp"
#include <cuda_runtime.h>
#include <algorithm>
#include <atomic>
#include <chrono>
#include <cstdio>
#include <stdexcept>
#include <vector>
#include <mutex>

namespace {
void ck(cudaError_t e){if(e!=cudaSuccess)throw std::runtime_error(cudaGetErrorString(e));}
void error_text(char* out,size_t size,const char* value){if(out&&size)std::snprintf(out,size,"%s",value);}
struct Buffer {uint32_t* words;uint32_t* counts;uint64_t capacity;unsigned slots;};
struct Parents {uint2* p[4];};
struct Context {
    int device,n;unsigned bits,slots,buckets;uint64_t capacity,bytes=0;
    Buffer a{},b{};Parents parents{};uint2* roots=nullptr;uint32_t* solutions=nullptr;
    unsigned* found=nullptr;unsigned long long* dropped=nullptr;
    cudaStream_t stream=nullptr;cudaEvent_t begin=nullptr,end=nullptr;
    std::vector<void*> owned;std::atomic<bool> cancelled{false};std::mutex lock;
    template<class T> T* alloc(size_t count){T* p=nullptr;ck(cudaMalloc(reinterpret_cast<void**>(&p),sizeof(T)*count));owned.push_back(p);bytes+=sizeof(T)*count;return p;}
    ~Context(){cudaSetDevice(device);if(stream)cudaStreamSynchronize(stream);for(auto p:owned)cudaFree(p);if(begin)cudaEventDestroy(begin);if(end)cudaEventDestroy(end);if(stream)cudaStreamDestroy(stream);}
    void init(){
        ck(cudaSetDevice(device));ck(cudaStreamCreateWithFlags(&stream,cudaStreamNonBlocking));
        ck(cudaEventCreate(&begin));ck(cudaEventCreate(&end));
        bits=unsigned(std::min(n/6,20));buckets=1U<<bits;capacity=uint64_t(buckets)*slots;
        size_t free=0,total=0;ck(cudaMemGetInfo(&free,&total));
        uint64_t need=capacity*(2*7*sizeof(uint32_t)+4*sizeof(uint2))+2ULL*buckets*4+65536;
        if(free<need+(256ULL<<20))throw std::runtime_error("Not enough free VRAM (144,5 with 64 slots requires about 5.51 GiB plus reserve). Stop other GPU workloads.");
        a={alloc<uint32_t>(7*capacity),alloc<uint32_t>(buckets),capacity,slots};
        b={alloc<uint32_t>(7*capacity),alloc<uint32_t>(buckets),capacity,slots};
        for(auto &p:parents.p)p=alloc<uint2>(capacity);
        roots=alloc<uint2>(256);solutions=alloc<uint32_t>(256*32);found=alloc<unsigned>(1);dropped=alloc<unsigned long long>(1);
    }
};
__device__ uint32_t read_word(Buffer b,unsigned word,uint32_t row){return b.words[uint64_t(word)*b.capacity+row];}
__device__ void write_word(Buffer b,unsigned word,uint32_t row,uint32_t value){b.words[uint64_t(word)*b.capacity+row]=value;}

template<unsigned N> __global__ void generate(nn::Seed seed,Buffer out,unsigned long long* dropped){
    constexpr unsigned C=N/6, B=(C<20?C:20), PER=512/N;
    constexpr uint32_t COUNT=1U<<(C+1);
    uint32_t group=blockIdx.x*blockDim.x+threadIdx.x;
    if(uint64_t(group)*PER>=COUNT)return;
    uint64_t digest[8];nn::leaf_digest(seed,group,digest);
    for(unsigned j=0;j<PER;++j){
        uint32_t leaf=group*PER+j;if(leaf>=COUNT)break;
        uint32_t h[6];
        #pragma unroll
        for(unsigned k=0;k<6;++k)h[k]=nn::chunk<C>(digest,j*(N/8)+k*(C/8));
        unsigned bucket=h[0]>>(C-B),slot=atomicAdd(out.counts+bucket,1U);
        if(slot>=out.slots){atomicAdd(dropped,1ULL);continue;}
        uint32_t row=bucket*out.slots+slot;
        #pragma unroll
        for(unsigned k=0;k<6;++k)write_word(out,k,row,h[k]);
        write_word(out,6,row,leaf);
    }
}

// A CUDA block processes complete buckets. Shared keys avoid repeatedly loading
// collision prefixes from global memory. Each unordered pair is examined once.
template<unsigned C,unsigned W,bool FIRST,bool FINAL>
__global__ void collide(Buffer in,Buffer out,uint2* parents,uint2* roots,unsigned* found,unsigned long long* dropped){
    __shared__ uint32_t keys[256],mins[256],last[256];
    uint32_t row=blockIdx.x*blockDim.x+threadIdx.x;
    unsigned slot=row%in.slots,bucket=row/in.slots;
    unsigned used=min(in.counts[bucket],in.slots);
    bool active=slot<used;unsigned tid=threadIdx.x,base=tid-slot;
    keys[tid]=active?read_word(in,0,row):0;
    mins[tid]=active?read_word(in,6,row):0;
    if(FINAL)last[tid]=active?read_word(in,1,row):0;
    __syncthreads();
    if(!active)return;
    for(unsigned j=slot+1;j<used;++j){
        if(keys[tid]!=keys[base+j]||mins[tid]==mins[base+j])continue;
        uint32_t other=bucket*in.slots+j;
        bool reverse=mins[tid]>mins[base+j];
        uint32_t left=reverse?other:row,right=reverse?row:other;
        if(FINAL){
            if(last[tid]!=last[base+j])continue;
            unsigned pos=atomicAdd(found,1U);
            if(pos<256)roots[pos]=make_uint2(left,right);
        }else{
            constexpr unsigned B=(C<20?C:20);
            uint32_t h[6];
            #pragma unroll
            for(unsigned k=1;k<W;++k)h[k-1]=read_word(in,k,row)^read_word(in,k,other);
            unsigned bucket2=h[0]>>(C-B),slot2=atomicAdd(out.counts+bucket2,1U);
            if(slot2>=out.slots){atomicAdd(dropped,1ULL);continue;}
            uint32_t dst=bucket2*out.slots+slot2;
            #pragma unroll
            for(unsigned k=0;k<W-1;++k)write_word(out,k,dst,h[k]);
            write_word(out,6,dst,min(mins[tid],mins[base+j]));
            parents[dst]=FIRST?make_uint2(read_word(in,6,left),read_word(in,6,right)):make_uint2(left,right);
        }
    }
}

__global__ void reconstruct(const uint2* roots,Parents parents,uint32_t* out,unsigned count){
    unsigned i=blockIdx.x*blockDim.x+threadIdx.x;if(i>=count)return;
    uint32_t a[32],b[32];a[0]=roots[i].x;a[1]=roots[i].y;unsigned width=2;
    for(int level=3;level>=0;--level){
        for(unsigned j=0;j<width;++j){uint2 p=parents.p[level][a[j]];b[j*2]=p.x;b[j*2+1]=p.y;}
        width*=2;for(unsigned j=0;j<width;++j)a[j]=b[j];
    }
    for(unsigned j=0;j<32;++j)out[i*32+j]=a[j];
}

template<unsigned N> void launch_round(Context& c,unsigned round,Buffer in,Buffer out){
    unsigned grid=unsigned(in.capacity/256);constexpr unsigned C=N/6;
    if(round==0)collide<C,6,true,false><<<grid,256,0,c.stream>>>(in,out,c.parents.p[0],c.roots,c.found,c.dropped);
    if(round==1)collide<C,5,false,false><<<grid,256,0,c.stream>>>(in,out,c.parents.p[1],c.roots,c.found,c.dropped);
    if(round==2)collide<C,4,false,false><<<grid,256,0,c.stream>>>(in,out,c.parents.p[2],c.roots,c.found,c.dropped);
    if(round==3)collide<C,3,false,false><<<grid,256,0,c.stream>>>(in,out,c.parents.p[3],c.roots,c.found,c.dropped);
    if(round==4)collide<C,2,false,true><<<grid,256,0,c.stream>>>(in,out,nullptr,c.roots,c.found,c.dropped);
}
float finish(Context& c){ck(cudaGetLastError());ck(cudaEventRecord(c.end,c.stream));ck(cudaEventSynchronize(c.end));float ms=0;ck(cudaEventElapsedTime(&ms,c.begin,c.end));return ms;}
}
extern "C" {
struct NNStats {double seconds;uint64_t dropped;uint32_t candidates;uint32_t truncated;uint64_t memory_bytes;double stages_ms[6];};
int nn_abi(){return 1;}
int nn_device_count(char* err,size_t len){try{int n=0;ck(cudaGetDeviceCount(&n));return n;}catch(const std::exception& e){error_text(err,len,e.what());return -1;}}
void* nn_create(int device,int n,unsigned slots,char* err,size_t len){
    Context* c=nullptr;
    try{
        if((n!=144&&n!=48)||(slots!=64&&slots!=128))throw std::runtime_error("n must be 144 or 48; slots must be 64 or 128");
        c=new Context;c->device=device;c->n=n;c->slots=slots;c->init();return c;
    }catch(const std::exception& e){error_text(err,len,e.what());delete c;return nullptr;}
}
void nn_destroy(void* ptr){delete static_cast<Context*>(ptr);}
void nn_cancel(void* ptr){if(ptr)static_cast<Context*>(ptr)->cancelled.store(true);}
int nn_solve(void* ptr,const uint8_t* input,const uint8_t* nonce,uint32_t* out,unsigned max_out,NNStats* stats,char* err,size_t len){
    try{
        if(!ptr||!input||!nonce||!out||!stats||max_out==0)throw std::runtime_error("invalid solve arguments");
        Context& c=*static_cast<Context*>(ptr);std::lock_guard<std::mutex> guard(c.lock);c.cancelled=false;
        *stats={};stats->memory_bytes=c.bytes;ck(cudaSetDevice(c.device));
        auto start=std::chrono::steady_clock::now();
        ck(cudaMemsetAsync(c.a.counts,0,c.buckets*4,c.stream));
        ck(cudaMemsetAsync(c.dropped,0,8,c.stream));ck(cudaMemsetAsync(c.found,0,4,c.stream));
        nn::Seed s=nn::seed(input,nonce,c.n);ck(cudaEventRecord(c.begin,c.stream));
        if(c.n==144)generate<144><<<((1U<<25)+2)/3/256+1,256,0,c.stream>>>(s,c.a,c.dropped);
        else generate<48><<<1,256,0,c.stream>>>(s,c.a,c.dropped);
        stats->stages_ms[0]=finish(c);Buffer in=c.a,outbuf=c.b;
        for(unsigned round=0;round<5;++round){
            if(c.cancelled.load())return 1;
            ck(cudaMemsetAsync(outbuf.counts,0,c.buckets*4,c.stream));ck(cudaEventRecord(c.begin,c.stream));
            if(c.n==144)launch_round<144>(c,round,in,outbuf);else launch_round<48>(c,round,in,outbuf);
            stats->stages_ms[round+1]=finish(c);std::swap(in,outbuf);
        }
        unsigned found=0;unsigned long long dropped=0;
        ck(cudaMemcpyAsync(&found,c.found,4,cudaMemcpyDeviceToHost,c.stream));
        ck(cudaMemcpyAsync(&dropped,c.dropped,8,cudaMemcpyDeviceToHost,c.stream));ck(cudaStreamSynchronize(c.stream));
        unsigned count=std::min(found,std::min(max_out,256U));
        if(count){reconstruct<<<(count+63)/64,64,0,c.stream>>>(c.roots,c.parents,c.solutions,count);ck(cudaGetLastError());ck(cudaMemcpyAsync(out,c.solutions,count*32*4,cudaMemcpyDeviceToHost,c.stream));ck(cudaStreamSynchronize(c.stream));}
        stats->candidates=count;stats->truncated=found>count;stats->dropped=dropped;
        stats->seconds=std::chrono::duration<double>(std::chrono::steady_clock::now()-start).count();return 0;
    }catch(const std::exception& e){error_text(err,len,e.what());return -1;}
}
}
