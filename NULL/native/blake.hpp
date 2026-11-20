// SPDX-License-Identifier: MIT
// NULL Native: BLAKE2b compression, RFC 7693. Original implementation.
#pragma once
#include <cstdint>
#include <cstring>
#ifdef __CUDACC__
#define NN_HD __host__ __device__ __forceinline__
#else
#define NN_HD inline
#endif
namespace nn {
NN_HD uint64_t rotr(uint64_t x,unsigned n){return (x>>n)|(x<<(64-n));}
NN_HD uint64_t iv(unsigned i){
    const uint64_t v[8]={0x6a09e667f3bcc908ULL,0xbb67ae8584caa73bULL,0x3c6ef372fe94f82bULL,0xa54ff53a5f1d36f1ULL,0x510e527fade682d1ULL,0x9b05688c2b3e6c1fULL,0x1f83d9abfb41bd6bULL,0x5be0cd19137e2179ULL};
    return v[i];
}
NN_HD uint64_t load64(const uint8_t* p){uint64_t x=0;for(unsigned i=0;i<8;++i)x|=uint64_t(p[i])<<(8*i);return x;}
NN_HD void mix(uint64_t& a,uint64_t& b,uint64_t& c,uint64_t& d,uint64_t x,uint64_t y){
    a=a+b+x;d=rotr(d^a,32);c+=d;b=rotr(b^c,24);
    a=a+b+y;d=rotr(d^a,16);c+=d;b=rotr(b^c,63);
}
NN_HD void compress(uint64_t h[8],const uint64_t m[16],uint64_t length,bool last){
    uint64_t v[16];for(unsigned i=0;i<8;++i){v[i]=h[i];v[i+8]=iv(i);}v[12]^=length;if(last)v[14]=~v[14];
#define NN_R(a,b,c,d,e,f,g,h_,i,j,k,l,n,o,p,q) \
    mix(v[0],v[4],v[8],v[12],m[a],m[b]);mix(v[1],v[5],v[9],v[13],m[c],m[d]); \
    mix(v[2],v[6],v[10],v[14],m[e],m[f]);mix(v[3],v[7],v[11],v[15],m[g],m[h_]); \
    mix(v[0],v[5],v[10],v[15],m[i],m[j]);mix(v[1],v[6],v[11],v[12],m[k],m[l]); \
    mix(v[2],v[7],v[8],v[13],m[n],m[o]);mix(v[3],v[4],v[9],v[14],m[p],m[q]);
    NN_R(0,1,2,3,4,5,6,7,8,9,10,11,12,13,14,15)
    NN_R(14,10,4,8,9,15,13,6,1,12,0,2,11,7,5,3)
    NN_R(11,8,12,0,5,2,15,13,10,14,3,6,7,1,9,4)
    NN_R(7,9,3,1,13,12,11,14,2,6,5,10,4,0,15,8)
    NN_R(9,0,5,7,2,4,10,15,14,1,11,12,6,8,3,13)
    NN_R(2,12,6,10,0,11,8,3,4,13,7,5,15,14,1,9)
    NN_R(12,5,1,15,14,13,4,10,0,7,6,3,9,2,8,11)
    NN_R(13,11,7,14,12,1,3,9,5,0,15,4,8,6,2,10)
    NN_R(6,15,14,9,11,3,0,8,12,2,13,7,1,4,10,5)
    NN_R(10,2,8,4,7,6,1,5,15,11,9,14,3,12,13,0)
    NN_R(0,1,2,3,4,5,6,7,8,9,10,11,12,13,14,15)
    NN_R(14,10,4,8,9,15,13,6,1,12,0,2,11,7,5,3)
#undef NN_R
    for(unsigned i=0;i<8;++i)h[i]^=v[i]^v[i+8];
}
struct Seed {uint64_t h[8];uint64_t tail[16];};
// pow_input is 113 bytes; nonce is 32 bytes. All 149-byte leaf messages
// share their first 128 bytes. Compress these ONCE on the host per nonce.
inline Seed seed(const uint8_t* input,const uint8_t* nonce,unsigned n){
    Seed s{};uint8_t bytes[256]{};std::memcpy(bytes,input,113);std::memcpy(bytes+113,nonce,32);
    for(unsigned i=0;i<8;++i)s.h[i]=iv(i);
    s.h[0]^=0x01010000U|((512/n)*n/8);
    const uint8_t prefix[8]={'n','u','l','l','P','o','W','_'};
    s.h[6]^=load64(prefix);s.h[7]^=uint64_t(n)|(uint64_t(5)<<32);
    uint64_t m[16];for(unsigned i=0;i<16;++i)m[i]=load64(bytes+8*i);
    compress(s.h,m,128,false);
    for(unsigned i=0;i<16;++i)s.tail[i]=load64(bytes+128+8*i);
    return s;
}
NN_HD void leaf_digest(const Seed& s,uint32_t group,uint64_t out[8]){
    uint64_t m[16];for(unsigned i=0;i<16;++i)m[i]=s.tail[i];
    // Last nonce byte occupies byte 16, LE32(group) occupies bytes 17..20.
    m[2]=(m[2]&255ULL)|(uint64_t(group)<<8);
    for(unsigned i=0;i<8;++i)out[i]=s.h[i];compress(out,m,149,true);
}
NN_HD uint8_t byte_at(const uint64_t* h,unsigned offset){return uint8_t(h[offset/8]>>(8*(offset%8)));}
template<unsigned C> NN_HD uint32_t chunk(const uint64_t* h,unsigned byte_offset){
    uint32_t v=0;for(unsigned j=0;j<C/8;++j)v=(v<<8)|byte_at(h,byte_offset+j);return v;
}
}
