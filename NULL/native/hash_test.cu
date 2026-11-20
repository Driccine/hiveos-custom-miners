// SPDX-License-Identifier: MIT
#include "blake.hpp"
#include <cuda_runtime.h>
#include <cstdio>
#include <stdexcept>
#include <vector>
extern "C" int nn_hash_host(const unsigned char* input,const unsigned char* nonce,int n,unsigned count,unsigned char* out){
    if((n!=48&&n!=144)||count>1024||!input||!nonce||!out)return -1;
    auto s=nn::seed(input,nonce,n);
    for(unsigned i=0;i<count;++i){uint64_t h[8];nn::leaf_digest(s,i,h);for(unsigned j=0;j<64;++j)out[i*64+j]=nn::byte_at(h,j);}return 0;
}
__global__ void hash_vectors(nn::Seed s,unsigned count,unsigned char* out){
    unsigned i=blockIdx.x*blockDim.x+threadIdx.x;if(i>=count)return;
    uint64_t h[8];nn::leaf_digest(s,i,h);for(unsigned j=0;j<64;++j)out[i*64+j]=nn::byte_at(h,j);
}
extern "C" int nn_hash_gpu(int device,const unsigned char* input,const unsigned char* nonce,int n,unsigned count,unsigned char* out,char* err,size_t errlen){
    unsigned char* data=nullptr;
    try{
        if((n!=48&&n!=144)||!count||count>1024||!input||!nonce||!out)throw std::runtime_error("invalid hash test arguments");
        auto check=[](cudaError_t e){if(e!=cudaSuccess)throw std::runtime_error(cudaGetErrorString(e));};
        check(cudaSetDevice(device));check(cudaMalloc(reinterpret_cast<void**>(&data),count*64));
        hash_vectors<<<(count+127)/128,128>>>(nn::seed(input,nonce,n),count,data);check(cudaGetLastError());
        check(cudaMemcpy(out,data,count*64,cudaMemcpyDeviceToHost));cudaFree(data);return 0;
    }catch(const std::exception& e){if(data)cudaFree(data);if(err&&errlen)std::snprintf(err,errlen,"%s",e.what());return -1;}
}
