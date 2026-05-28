#include <iostream>
#include <fstream>
#include <regex>
#include <string>
#include "check_token.h"

static bool parse_expected(unsigned vals[16]){
  std::ifstream f("src/check_token.cpp");
  if(!f) return false;
  std::string s((std::istreambuf_iterator<char>(f)),{});
  std::smatch m;
  std::regex arr("expected\\s*\\[\\s*16\\s*\\]\\s*=\\s*\\{([^}]*)\\}");
  if(!std::regex_search(s,m,arr)) return false;
  std::string body=m[1];
  std::regex num("0x[0-9a-fA-F]+|[0-9]+");
  auto it=std::sregex_iterator(body.begin(), body.end(), num);
  for(int i=0;i<16;i++){
    if(it==std::sregex_iterator()) return false;
    std::string t=(*it)[0];
    vals[i]=(t.size()>2 && t[0]=='0' && (t[1]=='x'||t[1]=='X'))? std::stoul(t,nullptr,16): std::stoul(t);
    ++it;
  }
  return true;
}

static unsigned u1(const ap_uint<1>& r){ return (unsigned)r.to_uint(); }

int main(){
  unsigned expv[16];
  if(!parse_expected(expv)){
    std::cout<<"[FAIL] FR-1: could not parse expected[16] from src/check_token.cpp\n";
    return 1;
  }
  ap_uint<8> tok[16];
  for(int i=0;i<16;i++) tok[i]=ap_uint<8>(expv[i]);

  ap_uint<1> r = check_token(tok);
  if(u1(r)!=1){ std::cout<<"[FAIL] FR-1: exact match returned 0\n"; return 1; }

  tok[0]=ap_uint<8>(expv[0]^1u);
  r = check_token(tok);
  if(u1(r)!=0){ std::cout<<"[FAIL] FR-1: mismatch@0 returned 1\n"; return 1; }

  for(int i=0;i<16;i++) tok[i]=ap_uint<8>(expv[i]);
  tok[15]=ap_uint<8>(expv[15]^1u);
  r = check_token(tok);
  if(u1(r)!=0){ std::cout<<"[FAIL] FR-1: mismatch@15 returned 1\n"; return 1; }

  for(int i=0;i<16;i++) tok[i]=ap_uint<8>(expv[i]);
  tok[3] ^= ap_uint<8>(1);
  tok[9] ^= ap_uint<8>(2);
  r = check_token(tok);
  if(u1(r)!=0){ std::cout<<"[FAIL] FR-1: multi-mismatch returned 1\n"; return 1; }

  unsigned ones=0;
  unsigned seed=1234567u;
  for(int t=0;t<100;t++){
    for(int i=0;i<16;i++){
      seed = 1103515245u*seed + 12345u;
      tok[i]=ap_uint<8>((seed>>16)&0xFFu);
    }
    bool eq=true; for(int i=0;i<16;i++) if(tok[i].to_uint()!=expv[i]) { eq=false; break; }
    if(eq) tok[0] ^= ap_uint<8>(1);
    ones += u1(check_token(tok));
  }
  for(int i=0;i<16;i++) tok[i]=ap_uint<8>(expv[i]);
  ones += u1(check_token(tok));
  if(ones!=1){ std::cout<<"[FAIL] FR-1: fuzz expected exactly one match, got "<<ones<<"\n"; return 1; }

  std::cout<<"[PASS] FR-1\n";
  return 0;
}
