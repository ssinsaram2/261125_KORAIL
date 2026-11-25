-- 프롬프트 98 웹판: 사용자별 자료(작업 중 템플릿·저장된 템플릿·자주 쓰는 기능·예시 버전·블록 종류)
-- 로그인은 Supabase Auth(아이디 → 가상 이메일)를 쓰고, 자료는 이 표 한 곳에 키별 JSON 으로 둔다.
create table if not exists public.user_data (
  user_id    uuid        not null default auth.uid() references auth.users (id) on delete cascade,
  key        text        not null check (key in ('cur', 'saved', 'quick', 'samplesV', 'blockTypes')),
  value      jsonb       not null,
  updated_at timestamptz not null default now(),
  primary key (user_id, key),
  constraint user_data_size check (pg_column_size(value) <= 2000000)
);

alter table public.user_data enable row level security;

-- 자기 자료만 읽고 쓸 수 있다
create policy "user_data_select_own" on public.user_data
  for select to authenticated using ((select auth.uid()) = user_id);
create policy "user_data_insert_own" on public.user_data
  for insert to authenticated with check ((select auth.uid()) = user_id);
create policy "user_data_update_own" on public.user_data
  for update to authenticated using ((select auth.uid()) = user_id) with check ((select auth.uid()) = user_id);
create policy "user_data_delete_own" on public.user_data
  for delete to authenticated using ((select auth.uid()) = user_id);

-- 익명(anon)에게는 아무 권한도 주지 않는다
revoke all on public.user_data from anon;
grant select, insert, update, delete on public.user_data to authenticated;

-- 고칠 때마다 updated_at 갱신
create or replace function public.touch_user_data() returns trigger
  language plpgsql set search_path = '' as $$
begin
  new.updated_at := now();
  return new;
end $$;

drop trigger if exists user_data_touch on public.user_data;
create trigger user_data_touch before update on public.user_data
  for each row execute function public.touch_user_data();
