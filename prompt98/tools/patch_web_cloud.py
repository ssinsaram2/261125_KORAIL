"""[1.4] 웹판에 Supabase 클라우드 로그인·저장을 붙인다 (한 번만 실행).

    python tools/patch_web_cloud.py [html 경로]

- 계정: Supabase Auth (아이디 → <아이디>@users.prompt98.app 가상 이메일, 이메일 확인 없음)
- 자료: public.user_data (사용자별 cur/saved/quick/samplesV/blockTypes, RLS 로 자기 것만)
- 브라우저에는 지금처럼 localStorage 에 두고(빠른 화면), 바뀐 키만 모아 0.8초 뒤 서버에 올린다.
- supabase-js 를 불러오지 못하면(오프라인) 예전처럼 이 브라우저 안 계정으로 동작한다.
- 이 브라우저에만 있던 예전 계정은 같은 아이디·비밀번호로 처음 로그인할 때 클라우드로 옮긴다.
"""
from __future__ import annotations

import sys
from pathlib import Path

HTML = Path(__file__).resolve().parents[2] / "프롬프트_템플릿_생성기.html"
SUPA_JS = "https://cdn.jsdelivr.net/npm/@supabase/supabase-js@2.45.4/dist/umd/supabase.js"


def rep(s: str, old: str, new: str) -> str:
    n = s.count(old)
    if n != 1:
        raise SystemExit(f"찾는 자리가 {n}곳이에요: {old[:70]!r}")
    return s.replace(old, new)


def main(path: Path):
    s = path.read_text(encoding="utf-8")
    if "SUPA_URL" in s:
        raise SystemExit("이미 클라우드 기능이 들어 있어요.")

    # 1) supabase-js
    s = rep(s, "\n<script>\n{\n", f'\n<script src="{SUPA_JS}"></script>\n<script>\n{{\n')

    # 2) store.set → 바뀐 사용자 키를 클라우드에 올릴 목록에 넣는다 + 클라우드 계층
    s = rep(s,
            "set(k,v){try{localStorage.setItem(sk(k),JSON.stringify(v));return true}catch(e){return false}}};",
            "set(k,v){try{localStorage.setItem(sk(k),JSON.stringify(v));cloud.mark(k);return true}catch(e){return false}}};\n"
            + CLOUD_JS)

    # 3) 로그인 화면 안내
    s = rep(s, '<p class="hint">계정과 템플릿은 이 브라우저에만 저장돼요.</p>',
            '<p class="hint" id="lgMode">계정과 템플릿은 이 브라우저에만 저장돼요.</p>')

    # 4) 로그인
    s = rep(s,
            "let u=null;try{u=await authenticate(uid,pw)}catch(err){lgErr(err.message);$('#lgGo').disabled=false;return}",
            "let u=null;try{u=sb?await cloudLogin(uid,pw):await authenticate(uid,pw);if(u&&sb)await cloudLoad(u)}"
            "catch(err){lgErr(netMsg(err));$('#lgGo').disabled=false;return}")

    # 5) 회원가입
    s = rep(s,
            "(async()=>{try{const u=await createUser(g('#suId'),g('#suPw'),g('#suName'),g('#suPw2'));close();enterApp(u)}",
            "(async()=>{try{const u=sb?await cloudSignup(g('#suId'),g('#suPw'),g('#suName'),g('#suPw2'))"
            ":await createUser(g('#suId'),g('#suPw'),g('#suName'),g('#suPw2'));if(sb)await cloudLoad(u,true);close();enterApp(u)}")
    s = rep(s, "<p>이 브라우저에서 쓸 계정을 만듭니다.<br>내 템플릿과 설정은 계정마다 따로 저장돼요.</p>",
            "<p>${sb?'계정을 만들면 어느 PC에서나 같은 아이디로<br>내 템플릿과 설정을 불러올 수 있어요.'"
            ":'이 브라우저에서 쓸 계정을 만듭니다.<br>내 템플릿과 설정은 계정마다 따로 저장돼요.'}</p>")
    s = rep(s, "msg(err.message||String(err),{icon:'warn',title:'회원가입'})",
            "msg(netMsg(err),{icon:'warn',title:'회원가입'})")

    # 6) 비밀번호 바꾸기
    s = rep(s,
            "(async()=>{try{const users=getUsers(),k=curUser.username.toLowerCase(),u=users[k];",
            "(async()=>{try{if(sb){await cloudPasswd(g('#cpOld'),g('#cpNew'),g('#cpNew2'));close();"
            "msg('비밀번호를 바꿨어요. 다음 로그인부터 새 비밀번호를 쓰세요.',{icon:'ok',title:'비밀번호 바꾸기'});return}\n"
            "        const users=getUsers(),k=curUser.username.toLowerCase(),u=users[k];")
    s = rep(s, "catch(err){msg(err.message||String(err),{icon:'warn',title:'비밀번호 바꾸기'})}",
            "catch(err){msg(netMsg(err),{icon:'warn',title:'비밀번호 바꾸기'})}")

    # 7) 로그아웃: 남은 변경을 올리고 세션을 끝낸다
    s = rep(s,
            "clearTimeout(saveT);store.set('ptg.cur',state);       // 지금 작업을 그 사용자 자리에 보관\n  curUser=null;",
            "clearTimeout(saveT);store.set('ptg.cur',state);       // 지금 작업을 그 사용자 자리에 보관\n"
            "  if(sb){const out=cloud.flush();out.finally(()=>{cloud.user=null;sb.auth.signOut().catch(()=>{})})}\n  curUser=null;")

    # 8) 첫 화면: 모드 안내
    s = rep(s, "renderAll();\nshowLogin();\n}\n</script>",
            "renderAll();\n$('#lgMode').textContent=sb?'☁ 계정과 템플릿은 클라우드에 저장돼 어느 PC에서나 이어서 쓸 수 있어요.'"
            ":'계정과 템플릿은 이 브라우저에만 저장돼요. (오프라인 모드)';\n"
            "addEventListener('pagehide',()=>{if(curUser&&sb){clearTimeout(saveT);store.set('ptg.cur',state);cloud.flush()}});\n"
            "showLogin();\n}\n</script>")

    path.write_text(s, encoding="utf-8", newline="")
    print("웹판에 클라우드 로그인·저장을 붙였어요:", path)


CLOUD_JS = r"""
/* ---------- [1.4] 클라우드 (Supabase) ----------
   계정은 Supabase Auth 에 <아이디>@users.prompt98.app 가상 이메일로 둔다(메일은 보내지 않음).
   사용자 자료는 user_data 표에 키별 JSON 으로 두고, 행 수준 보안(RLS)으로 자기 것만 읽고 쓴다.
   화면은 지금처럼 localStorage 를 쓰고, 바뀐 키만 모아 0.8초 뒤 서버에 올린다. */
const SUPA_URL='%%SUPA_URL%%',SUPA_KEY='%%SUPA_KEY%%',MAIL_DOMAIN='users.prompt98.app';
const sb=(()=>{try{return window.supabase&&/^https:\/\/\w+\.supabase\.co$/.test(SUPA_URL)
  ?window.supabase.createClient(SUPA_URL,SUPA_KEY,{auth:{persistSession:false,autoRefreshToken:true,detectSessionInUrl:false}}):null}catch(e){return null}})();
const CLOUD_KEYS=['cur','saved','quick','samplesV','blockTypes'];
const ukey=(u,key)=>`ptg.u.${u.username.toLowerCase()}.${key}`;
const cloud={user:null,dirty:new Set(),t:null,warned:false,busy:null,
  mark(k){if(!sb||!this.user||!UKEYS.has(k))return;this.dirty.add(k.slice(4));clearTimeout(this.t);this.t=setTimeout(()=>this.flush(),800)},
  async flush(){
    if(!sb||!this.user)return;
    if(this.busy){await this.busy.catch(()=>{});}
    if(!this.dirty.size)return;clearTimeout(this.t);
    const u=this.user,keys=[...this.dirty];this.dirty.clear();
    const rows=[];keys.forEach(key=>{try{const v=JSON.parse(localStorage.getItem(ukey(u,key)));if(v!=null)rows.push({user_id:u.id,key,value:v})}catch(e){}});
    if(!rows.length)return;
    this.busy=sb.from('user_data').upsert(rows,{onConflict:'user_id,key'}).then(({error})=>{
      if(!error){if(this.warned){this.warned=false;flash('클라우드에 다시 저장했어요')}return}
      keys.forEach(k=>this.dirty.add(k));
      if(!this.warned){this.warned=true;flash('클라우드에 저장하지 못했어요. 이 브라우저에는 저장돼 있고, 잠시 뒤 다시 시도합니다.')}
      clearTimeout(this.t);this.t=setTimeout(()=>this.flush(),15000)});
    try{await this.busy}finally{this.busy=null}
  }};
const mailOf=uid=>`${uid.trim().toLowerCase()}@${MAIL_DOMAIN}`;
const userOf=au=>({id:au.id,username:(au.user_metadata||{}).username||au.email.split('@')[0],name:(au.user_metadata||{}).name||''});
function netMsg(err){
  const m=String((err&&err.message)||err||'');
  if(/fetch|network|Failed to|NetworkError|Load failed/i.test(m))return '서버에 연결하지 못했어요. 인터넷 연결을 확인한 뒤 다시 시도해 주세요.';
  return m||'알 수 없는 오류가 났어요.';
}
/* 로그인: 클라우드 계정 → 없으면 이 브라우저의 예전 계정을 같은 아이디·비밀번호로 클라우드에 옮긴다 */
async function cloudLogin(uid,pw){
  const {data,error}=await sb.auth.signInWithPassword({email:mailOf(uid),password:pw});
  if(!error)return userOf(data.user);
  if(error.status&&error.status>=500)throw error;
  if(!/invalid/i.test(error.message||'')&&error.code!=='invalid_credentials')throw error;
  const old=await authenticate(uid,pw);if(!old)return null;
  const u=await cloudSignup(old.username,pw,old.name||'',pw,true);
  u.migrated=true;return u;
}
async function cloudSignup(uid,pw,name,cf,migrating){
  uid=String(uid).trim();name=String(name||'').replace(/\s+/g,' ').trim().slice(0,20);
  if(!UNAME.test(uid))throw new Error('아이디는 영문·숫자·밑줄(_)로 4~20자, 띄어쓰기 없이 지어 주세요.');
  if(!migrating){const e=pwError(pw,cf,uid);if(e)throw new Error(e)}
  const {data,error}=await sb.auth.signUp({email:mailOf(uid),password:pw,options:{data:{username:uid,name}}});
  if(error){
    if(error.code==='user_already_exists'||/already/i.test(error.message||''))
      throw new Error(migrating?'이 아이디는 클라우드에서 이미 다른 분이 쓰고 있어요. 새 아이디로 가입해 주세요.':'이미 쓰고 있는 아이디예요. 다른 아이디를 골라 주세요.');
    if(error.code==='weak_password')throw new Error('비밀번호가 너무 쉬워요. 8자 이상, 영문과 숫자를 함께 넣어 주세요.');
    if(error.status===429)throw new Error('가입 요청이 너무 많아요. 잠시 뒤 다시 시도해 주세요.');
    throw error;
  }
  if(!data.session)throw new Error('가입은 됐지만 바로 로그인할 수 없어요. 관리자에게 이메일 확인 설정을 문의해 주세요.');
  return userOf(data.user);
}
/* 로그인 직후: 서버 자료를 이 브라우저에 내려받는다. 서버가 비어 있으면(새 계정·옮긴 계정) 이 브라우저 자료를 올린다 */
async function cloudLoad(u,fresh){
  cloud.user=u;cloud.dirty.clear();
  if(fresh){   // 로그인 기능 전(주인 없는) 자료는 이 브라우저의 첫 클라우드 가입자에게
    let claimed=false;try{claimed=!!localStorage.getItem('ptg.claimed')}catch(e){}
    if(!claimed){UKEYS.forEach(key=>{const v=localStorage.getItem(key),to=ukey(u,key.slice(4));if(v!=null&&localStorage.getItem(to)==null)localStorage.setItem(to,v)});
      try{localStorage.setItem('ptg.claimed','1')}catch(e){}}
  }
  const {data,error}=await sb.from('user_data').select('key,value');
  if(error)throw error;
  if(data.length){data.forEach(r=>{try{localStorage.setItem(ukey(u,r.key),JSON.stringify(r.value))}catch(e){}});return}
  CLOUD_KEYS.forEach(key=>{if(localStorage.getItem(ukey(u,key))!=null)cloud.dirty.add(key)});
  await cloud.flush();
}
async function cloudPasswd(oldPw,pw,cf){
  const re=await sb.auth.signInWithPassword({email:mailOf(curUser.username),password:oldPw});
  if(re.error){if(re.error.status>=500)throw re.error;throw new Error('지금 비밀번호가 맞지 않아요.')}
  const e=pwError(pw,cf,curUser.username);if(e)throw new Error(e);
  const {error}=await sb.auth.updateUser({password:pw});
  if(error){if(error.code==='same_password')throw new Error('지금 비밀번호와 다른 비밀번호로 정해 주세요.');throw error}
}"""

if __name__ == "__main__":
    main(Path(sys.argv[1]) if len(sys.argv) > 1 else HTML)
