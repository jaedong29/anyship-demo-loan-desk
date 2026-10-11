# Loan Desk · 빌려쓰는 사이

동아리 공용 물품을 **등록 → 대여 → 반납**하는 작은 ORM 데모입니다. 팀 배정 앱과는 별개이며, 팀원이 이 개인 저장소를 fork하여 수정하고 AnyShip 배포 대상으로 사용할 수 있습니다.

Python 3.12 / FastAPI / SQLAlchemy 2 ORM / PostgreSQL. 별도 프런트 빌드나 외부 API 없이 한 컨테이너에서 한국어 화면과 API를 제공합니다. 로그인 없는 공유 시연 앱이므로 가상의 이름만 입력하세요.

## 로컬 실행

Docker와 Docker Compose가 필요합니다.

```bash
git clone https://github.com/jaedong29/anyship-demo-loan-desk.git
cd anyship-demo-loan-desk
cp .env.example .env
docker compose -p loan-desk-local -f compose.local.yaml up --build -d
```

http://127.0.0.1:18086/ 에서 물품을 등록한 뒤 빌리고 반납하세요. DB 준비 → 일회성 테이블 초기화 → 웹 실행 순서로 시작합니다. `.env.example`의 비밀번호는 로컬용 더미이며 실제 배포에는 사용하지 않습니다.

```bash
curl http://127.0.0.1:18086/healthz
docker compose -p loan-desk-local -f compose.local.yaml logs web
docker compose -p loan-desk-local -f compose.local.yaml restart web
```

재시작 뒤에도 DB 기록이 유지됩니다. 종료는 `docker compose -p loan-desk-local -f compose.local.yaml down`입니다. `down -v`는 이 로컬 데모의 DB 볼륨과 데이터를 삭제하므로 초기화할 때만 사용하세요.

## ORM과 데이터 처리

- `app/models.py`: 물품과 대여 기록을 ORM 모델로 정의합니다.
- `app/db.py`: 환경변수 `DATABASE_URL`로 PostgreSQL에 연결하고 요청마다 Session을 만듭니다. SQLite 폴백은 없습니다.
- `app/main.py`: 등록·대여·반납을 트랜잭션으로 처리합니다. 대여 시 물품 행, 반납 시 대여 기록과 물품 행을 잠가 재고 부족과 중복 반납을 방지합니다.
- `app/migrate.py`: `python -m app.migrate`로 새 앱의 테이블을 생성합니다. 반복 실행해도 기존 기록을 지우지 않습니다. 기존 열 변경이나 데이터 이전을 수행하는 마이그레이션 도구는 아닙니다.
- `/healthz`: DB 연결과 두 테이블 조회까지 성공하면 200입니다. DB 중단 또는 테이블 미초기화 시 503입니다.

## 현재 AnyShip main에 배포

확인 기준: `gumtiket/anyship` main `ad371ad6fedb5aa2a1a92050a5a056ba190990dc`.

1. 개인 계정으로 fork하고 GitHub App의 접근 허용 저장소에 추가합니다.
2. 루트 `deploy-spec.yaml`의 `source.repo`를 fork 주소로 바꾸고 변경을 병합합니다.
3. AnyShip 프로젝트에 fork URL을 연결합니다.
4. 연결이 확인된 **AWS 상시 실행** 또는 **온프레미스** 환경을 선택하고 배포합니다.
5. 공개 URL에서 물품 등록 → 대여 → 반납을 확인합니다.

루트의 Dockerfile과 배포 명세가 이미 포함되어 있어 배포를 위해 AI가 DB 저장 방식을 바꿀 필요가 없습니다. 현재 어댑터는 AWS 상시 실행에서 앱 전용 RDS DB를, 온프레미스에서 앱 전용 PostgreSQL 컨테이너를 연결합니다. 두 경로 모두 `DATABASE_URL`을 주입하고 `release.migrate: python -m app.migrate`를 실행해야 합니다. `env`에 DATABASE_URL이나 PORT를 별도로 넣지 않습니다.

### AI 분석 시 확인할 현재 한계

현재 엔진은 기존 PostgreSQL 사용만으로 `backing_services`와 `release.migrate`를 생성하지 않습니다. SQLite 변환을 처리한 경우에 외부 DB를 생성 명세에 반영하는 구조입니다. 따라서 이 앱을 분석한 뒤 생성된 `deploy-spec.yaml`을 그대로 덮어쓰면 DB 선언과 초기화 명령이 사라질 수 있습니다.

**AI가 제안한 배포 명세를 그대로 병합하지 마세요.** fork의 다음 두 선언을 보존한 상태로 검토·병합해야 합니다. 성공 시연은 제공한 명세로 배포하는 흐름이며, 이 기존 명세 보존 문제를 해결한 AI 엔진을 포함하지 않습니다.

```yaml
backing_services:
  - type: postgres
    bind_as: DATABASE_URL
release:
  migrate: python -m app.migrate
```

웹 AI 분석은 `no_gate=True`로 실행되므로 분석 성공과 실제 앱 실행·배포 성공은 다릅니다. 실제 모델 호출을 확인하지 않은 결과를 Anthropic 성공으로 설명하지 마세요.

### 서비스 환경의 사전 조건

정상 GitHub 연동, Docker·Git·SSH 실행 환경, 서비스 SSH 개인/공개 키, 대상 서버 `deploy` 계정의 키 인증, 접근 가능한 포트, DNS/TLS가 필요합니다. 온프레미스 준비 스크립트는 현재 Amazon Linux 2023 x86_64·공인 IPv4 대상으로 작성되어 있습니다. 앱 코드로 SSH 설정 문제를 해결하지 않습니다.

## 테스트

테스트는 실행 중인 **별도의 로컬 데모 DB**에 기록을 추가합니다. 실제 배포 DB에서 실행하지 마세요.

```bash
python3.12 -m venv .venv
.venv/bin/python -m pip install -r requirements-dev.txt
TEST_BASE_URL=http://127.0.0.1:18086 .venv/bin/python -m pytest -q
```

기능, 잘못된 입력, 동일 물품 중복 등록, 8개 동시 대여 요청, 2개 동시 반납 요청을 검사합니다. 실제 검증 결과와 한계는 `VERIFICATION.md`를 참고하세요.

## 3분 시연

1. fork한 저장소와 PostgreSQL·초기화 명령이 포함된 배포 명세를 보여줍니다.
2. 연결이 확인된 환경에 배포하고 공개 URL을 엽니다. AWS 기반 생성이 필요하면 시연 전에 준비합니다.
3. `무선 마이크` 2개를 등록하고 가상 참가자 이름으로 1개를 빌립니다.
4. 대여 가능 수량 감소와 대여 기록을 보여주고 반납합니다.
5. 화면 새로고침 뒤 기록이 남는 것을 보여줍니다. 재시작 후 영속성은 사전 검증 결과로 설명할 수 있습니다.

SQLAlchemy Session과 트랜잭션 구현은 [공식 문서](https://docs.sqlalchemy.org/en/20/orm/session_basics.html)를 참고했습니다.

MIT License. 팀 저장소와 독립된 개인 데모입니다.
