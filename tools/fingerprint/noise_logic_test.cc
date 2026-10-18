#include <cstdint>
#include <cstddef>
#include <cstdio>
#include <vector>
#include <limits>
#include <cmath>
#include <cstdlib>
namespace base { template<class T> struct CheckedNumeric { unsigned __int128 v; bool ok=true; CheckedNumeric(T x):v(x){} CheckedNumeric& operator*=(size_t m){v*=m; if(v>std::numeric_limits<size_t>::max()) ok=false; return *this;} CheckedNumeric& operator+=(size_t m){v+=m; if(v>std::numeric_limits<size_t>::max()) ok=false; return *this;} bool IsValid() const {return ok;} size_t ValueOrDie() const {return (size_t)v;} }; }
constexpr uint64_t kFnvOffset = 0xcbf29ce484222325ull;
constexpr uint64_t kFnvPrime = 0x100000001b3ull;

uint64_t Mix(uint64_t z) {
  z += 0x9e3779b97f4a7c15ull;
  z = (z ^ (z >> 30)) * 0xbf58476d1ce4e5b9ull;
  z = (z ^ (z >> 27)) * 0x94d049bb133111ebull;
  return z ^ (z >> 31);
}

void SwiftraNoiseRGBA8(uint64_t key,
                       uint8_t* data,
                       size_t capacity,
                       int width,
                       int height,
                       size_t row_bytes,
                       int x0,
                       int y0,
                       bool bgra) {
  if (!key || !data || width <= 0 || height <= 0) {
    return;
  }
  base::CheckedNumeric<size_t> needed = static_cast<size_t>(height - 1);
  needed *= row_bytes;
  needed += static_cast<size_t>(width) * 4;
  if (!needed.IsValid() || needed.ValueOrDie() > capacity ||
      row_bytes < static_cast<size_t>(width) * 4) {
    return;
  }
  const int r = bgra ? 2 : 0;
  const int b = bgra ? 0 : 2;
  for (int y = 0; y < height; ++y) {
    uint8_t* row = data + static_cast<size_t>(y) * row_bytes;
    for (int x = 0; x < width; ++x) {
      uint8_t* p = row + static_cast<size_t>(x) * 4;
      if (p[3] != 255) {
        continue;  // transparent / anti-aliased edges stay exact
      }
      const uint64_t color = static_cast<uint64_t>(p[r] & 0xfe) |
                             (static_cast<uint64_t>(p[1] & 0xfe) << 8) |
                             (static_cast<uint64_t>(p[b] & 0xfe) << 16);
      const uint64_t pos =
          (static_cast<uint64_t>(static_cast<uint32_t>(x0 + x)) << 32) |
          static_cast<uint32_t>(y0 + y);
      const uint64_t h = Mix(Mix(pos) ^ color ^ key);
      if ((h & 0xf) != 0) {
        continue;
      }
      const uint64_t pick = (h >> 8) % 3;
      const int index = pick == 0 ? r : (pick == 1 ? 1 : b);
      p[index] = static_cast<uint8_t>((p[index] & 0xfe) | ((h >> 16) & 1));
    }
  }
}

void SwiftraNoiseAudio(uint64_t key,
                       float* samples,
                       size_t count,
                       uint32_t channel) {
  if (!key || !samples) {
    return;
  }
  // Per-site gain in (-2^-16, 2^-16) plus +-2^-18 per-sample jitter.
  const double gain =
      1.0 + (static_cast<double>(Mix(key) >> 11) / 9007199254740992.0 - 0.5) *
                (2.0 / 65536.0);
  for (size_t i = 0; i < count; ++i) {
    const uint64_t h =
        Mix(key ^ Mix((static_cast<uint64_t>(channel) << 40) ^ i));
    const double jitter = (h & 1) ? (1.0 / 262144.0) : (-1.0 / 262144.0);
    samples[i] = static_cast<float>(samples[i] * (gain + jitter));
  }
}


int main(){
  const int W=100,H=60; std::vector<uint8_t> img(W*H*4);
  for(int i=0;i<W*H;i++){img[i*4]=200;img[i*4+1]=100;img[i*4+2]=51;img[i*4+3]=255;}
  for(int i=0;i<W;i++) img[i*4+3]=128; // first row semi-transparent
  auto a=img, b=img, c=img;
  uint64_t k1=Mix(1)|1, k2=Mix(2)|1;
  SwiftraNoiseRGBA8(k1,a.data(),a.size(),W,H,W*4,0,0,false);
  SwiftraNoiseRGBA8(k2,b.data(),b.size(),W,H,W*4,0,0,false);
  int changed=0,maxd=0,row0=0; for(size_t i=0;i<img.size();i++){int d=abs(a[i]-img[i]); if(d){changed++; if(i<(size_t)W*4) row0++;} if(d>maxd)maxd=d;}
  int diffk=0; for(size_t i=0;i<img.size();i++) if(a[i]!=b[i]) diffk++;
  auto a2=a; SwiftraNoiseRGBA8(k1,a2.data(),a2.size(),W,H,W*4,0,0,false); int idem=0; for(size_t i=0;i<a.size();i++) if(a[i]!=a2[i]) idem++;
  // sub-rect consistency: noise a 10x10 region at (30,20) separately
  std::vector<uint8_t> sub(10*10*4); for(int y=0;y<10;y++)for(int x=0;x<10;x++)for(int ch=0;ch<4;ch++) sub[(y*10+x)*4+ch]=img[((20+y)*W+30+x)*4+ch];
  SwiftraNoiseRGBA8(k1,sub.data(),sub.size(),10,10,40,30,20,false); int subd=0; for(int y=0;y<10;y++)for(int x=0;x<10;x++)for(int ch=0;ch<4;ch++) if(sub[(y*10+x)*4+ch]!=a[((20+y)*W+30+x)*4+ch]) subd++;
  // capacity guard
  std::vector<uint8_t> small(16); SwiftraNoiseRGBA8(k1,small.data(),small.size(),W,H,W*4,0,0,false);
  printf("changed_bytes=%d (of %d px) maxdiff=%d semi_transparent_changed=%d keys_differ_bytes=%d idempotent_diff=%d subrect_diff=%d\n",changed,W*H,maxd,row0,diffk,idem,subd);
  std::vector<float> s1(1000,0.5f), s2=s1; SwiftraNoiseAudio(k1,s1.data(),s1.size(),0); SwiftraNoiseAudio(k2,s2.data(),s2.size(),0);
  double sum0=0,sum1=0,sum2=0,maxrel=0; for(int i=0;i<1000;i++){sum0+=0.5;sum1+=s1[i];sum2+=s2[i]; double r=fabs(s1[i]-0.5)/0.5; if(r>maxrel)maxrel=r;}
  printf("audio sum0=%.9f k1=%.9f k2=%.9f maxrel=%.3g\n",sum0,sum1,sum2,maxrel);
}
