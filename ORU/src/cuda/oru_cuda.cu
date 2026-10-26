// ORU/RIGOR standalone NVIDIA nonce scanner. Original implementation; no third-party miner.
// Consensus PoW: SHA3-256("RGRPOW01" || 80-byte header), output compared little endian.
// INPUT: --header <160-hex> --target <64-hex-big-endian> --start N --count N
// OUTPUT: "FOUND <nonce> <attempts>" or "NONE <attempts>".
// No networking in this binary; SOLO coordinator handles GBT/submitblock.
#include <cuda_runtime.h>
#include <cstdint>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <algorithm>
#include <chrono>
#include <stdexcept>
#include <string>
#include <vector>

__constant__ uint64_t d_base[11], d_target[4];
__constant__ uint64_t d_rc[24] = {
    0x0000000000000001ULL,0x0000000000008082ULL,0x800000000000808aULL,
    0x8000000080008000ULL,0x000000000000808bULL,0x0000000080000001ULL,
    0x8000000080008081ULL,0x8000000000008009ULL,0x000000000000008aULL,
    0x0000000000000088ULL,0x0000000080008009ULL,0x000000008000000aULL,
    0x000000008000808bULL,0x800000000000008bULL,0x8000000000008089ULL,
    0x8000000000008003ULL,0x8000000000008002ULL,0x8000000000000080ULL,
    0x000000000000800aULL,0x800000008000000aULL,0x8000000080008081ULL,
    0x8000000000008080ULL,0x0000000080000001ULL,0x8000000080008008ULL
};
__constant__ int d_rotation[24] = {1,3,6,10,15,21,28,36,45,55,2,14,27,41,56,8,25,43,62,18,39,61,20,44};
__constant__ int d_pi[24] = {10,7,11,17,18,3,5,16,8,21,24,4,15,23,19,13,12,2,20,14,22,9,6,1};

__device__ __forceinline__ uint64_t rol(uint64_t v, int n) {
    return (v << n) | (v >> (64-n));
}
__device__ __forceinline__ bool under_target(const uint64_t a[25]) {
    // Digest bytes are interpreted as a little-endian uint256.
    for (int i=3;i>=0;--i) {
        if (a[i] < d_target[i]) return true;
        if (a[i] > d_target[i]) return false;
    }
    return true;
}
__global__ void scan(uint32_t begin, uint32_t count, uint32_t* result) {
    const uint32_t i = blockIdx.x * blockDim.x + threadIdx.x;
    if (i >= count) return;
    const uint32_t nonce = begin + i; // intentionally wraps as uint32_t
    uint64_t a[25] = {};
    #pragma unroll
    for(int k=0;k<11;++k) a[k] = d_base[k];
    a[10] = (a[10] & 0x00000000ffffffffULL) | (uint64_t(nonce) << 32);
    a[11] ^= 0x06ULL;                 // FIPS 202 SHA3 domain suffix
    a[16] ^= 0x8000000000000000ULL; // byte 135 of 136-byte rate
    uint64_t bc[5];
    for(int r=0;r<24;++r) {
        #pragma unroll
        for(int x=0;x<5;++x)
            bc[x]=a[x]^a[x+5]^a[x+10]^a[x+15]^a[x+20];
        #pragma unroll
        for(int x=0;x<5;++x) {
            const uint64_t t=bc[(x+4)%5]^rol(bc[(x+1)%5],1);
            #pragma unroll
            for(int y=0;y<25;y+=5) a[y+x]^=t;
        }
        uint64_t last=a[1];
        for(int x=0;x<24;++x) {
            int ix=d_pi[x];
            uint64_t tmp=a[ix];
            a[ix]=rol(last,d_rotation[x]);
            last=tmp;
        }
        #pragma unroll
        for(int y=0;y<25;y+=5) {
            #pragma unroll
            for(int x=0;x<5;++x) bc[x]=a[y+x];
            #pragma unroll
            for(int x=0;x<5;++x) a[y+x]^=(~bc[(x+1)%5])&bc[(x+2)%5];
        }
        a[0]^=d_rc[r];
    }
    if(under_target(a)) {
        // Only one winner returned per batch. Host verifies hash before submission.
        if(atomicCAS(&result[0],0U,1U)==0U) result[1]=nonce;
    }
}
static void ck(cudaError_t e,const char* w) {
    if(e!=cudaSuccess) { std::fprintf(stderr,"CUDA %s: %s\n",w,cudaGetErrorString(e)); std::exit(2); }
}
static int hexdigit(char c) {
    if(c>='0'&&c<='9')return c-'0';
    if(c>='a'&&c<='f')return c-'a'+10;
    if(c>='A'&&c<='F')return c-'A'+10;
    throw std::invalid_argument("invalid hex character");
}
static std::vector<uint8_t> hexbytes(const std::string& s,size_t n) {
    if(s.size()!=2*n) throw std::invalid_argument("wrong hex length");
    std::vector<uint8_t> out(n);
    for(size_t i=0;i<n;++i) out[i]=(hexdigit(s[2*i])<<4)|hexdigit(s[2*i+1]);
    return out;
}
static uint64_t le64(const uint8_t* b) {
    uint64_t v=0;
    for(int i=0;i<8;++i)v|=uint64_t(b[i])<<(i*8);
    return v;
}
static uint64_t number(const char* s) {
    char* end=nullptr;
    unsigned long long v=std::strtoull(s,&end,10);
    if(!s[0] || !end || *end) throw std::invalid_argument("invalid unsigned number");
    return uint64_t(v);
}
int main(int argc,char** argv) {
    try {
        std::string header,target;
        uint64_t start=0,count=0,batch=1048576;
        int device=0;
        for(int i=1;i<argc;++i) {
            std::string arg=argv[i];
            if(i+1>=argc) throw std::invalid_argument("missing value: "+arg);
            std::string value=argv[++i];
            if(arg=="--header")header=value;
            else if(arg=="--target")target=value;
            else if(arg=="--start")start=number(value.c_str());
            else if(arg=="--count")count=number(value.c_str());
            else if(arg=="--batch")batch=number(value.c_str());
            else if(arg=="--device")device=int(number(value.c_str()));
            else throw std::invalid_argument("unknown option "+arg);
        }
        if(start>0xffffffffULL || count<1 || count>0x100000000ULL || batch<1 || batch>16777216ULL)
            throw std::invalid_argument("invalid nonce range or batch");
        const auto head=hexbytes(header,80);
        const auto t=hexbytes(target,32);
        uint8_t input[88]={};
        std::memcpy(input,"RGRPOW01",8);
        std::memcpy(input+8,head.data(),80);
        uint64_t base[11],targetWords[4];
        for(int i=0;i<11;++i) base[i]=le64(input+8*i);
        for(int i=0;i<4;++i) {
            uint8_t b[8];
            for(int j=0;j<8;++j) b[j]=t[31-(i*8+j)];
            targetWords[i]=le64(b);
        }
        ck(cudaSetDevice(device),"set device");
        ck(cudaMemcpyToSymbol(d_base,base,sizeof(base)),"copy input");
        ck(cudaMemcpyToSymbol(d_target,targetWords,sizeof(targetWords)),"copy target");
        uint32_t* d_result=nullptr;
        ck(cudaMalloc(&d_result,2*sizeof(uint32_t)),"allocate result");
        uint64_t processed=0;
        while(processed<count) {
            uint32_t thisCount=uint32_t(std::min(batch,count-processed));
            ck(cudaMemset(d_result,0,2*sizeof(uint32_t)),"reset result");
            constexpr int threads=256;
            scan<<<(thisCount+threads-1)/threads,threads>>>(uint32_t(start+processed),thisCount,d_result);
            ck(cudaGetLastError(),"launch");
            uint32_t found[2]={0,0};
            ck(cudaMemcpy(found,d_result,sizeof(found),cudaMemcpyDeviceToHost),"read result");
            if(found[0]) {
                // Return the exact number of attempted candidates only as an upper bound.
                std::printf("FOUND %u %llu\n",found[1],(unsigned long long)(processed+thisCount));
                ck(cudaFree(d_result),"free");
                return 0;
            }
            processed+=thisCount;
        }
        ck(cudaFree(d_result),"free");
        std::printf("NONE %llu\n",(unsigned long long)processed);
        return 0;
    } catch(const std::exception& e) {
        std::fprintf(stderr,"ORU CUDA: %s\n",e.what());
        return 2;
    }
}
