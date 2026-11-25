-- 템플릿마다 "첫 문장(아래의 지시사항에 따라 결과물을 생성해줘.)"을 붙일지 여부. 기존 템플릿은 켜짐.
ALTER TABLE templates ADD COLUMN intro INTEGER NOT NULL DEFAULT 1 CHECK (intro IN (0,1));

PRAGMA user_version = 2;
