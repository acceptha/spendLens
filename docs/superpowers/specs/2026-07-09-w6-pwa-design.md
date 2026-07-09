# W6 — 설치형 PWA / 모바일 설계

> 작성일: 2026-07-09 · 트랙: PWA/모바일 (범위 A = 설치형)

## 목표

웹앱(`apps/web`)을 설치 가능한 PWA로 만든다. 홈 화면 추가 · standalone 실행 · 앱 셸 오프라인 로드 · iOS/Android 설치 메타 보강. 웹 푸시와 런타임 데이터 오프라인 캐싱은 비목표(별도).

## 현재 상태

`index.html`은 뷰포트 meta만 있는 최소 구성. `public/`·매니페스트·서비스워커·아이콘·`vite-plugin-pwa` 전부 없음. PWA 그린필드.

## 설계

### 1. 도구 — `vite-plugin-pwa` (Workbox)

`pnpm add -D vite-plugin-pwa`. 매니페스트 + 서비스워커 + 프리캐시 + 업데이트 라이프사이클을 자동 처리(수제 SW의 stale 캐시/업데이트 버그 회피).

`vite.config.ts` `plugins`에 `VitePWA({...})` 추가:
- `registerType: "autoUpdate"` — 새 배포 시 SW 자동 갱신.
- `manifest`: `name`/`short_name` "SpendLens", `lang: "ko"`, `theme_color: "#2563eb"`(blue-600), `background_color: "#09090b"`(zinc-950), `display: "standalone"`, `start_url: "/"`, `icons`(192·512·512-maskable).
- `workbox.globPatterns`: 빌드 산출물(js/css/html/ico/png/svg) 프리캐시 → 앱 셸 오프라인 로드.
- 기존 `test`(vitest)·`resolve.extensions`·`react()` 설정과 공존(빌드 전용 플러그인이라 vitest 무영향).

### 2. 아이콘 — `public/`

소스 SVG 1개(다크 라운드스퀘어 + 브랜드 심볼)로부터 PNG 세트 생성:
- `pwa-192x192.png`, `pwa-512x512.png`, `pwa-maskable-512x512.png`, `apple-touch-icon.png`(180), `favicon.ico`/`favicon.svg`.
- 생성 방법(우선순위): ① `@vite-pwa/assets-generator`(소스→전 사이즈 rasterize) → ② 실패 시 Python/Pillow 간단 드로잉 → ③ 그래도 안 되면 SVG 아이콘 + 최소 PNG 수제(안드로이드 우선, iOS degraded)로 대체하고 한계 명시.

### 3. `index.html` 메타

`theme-color`, `apple-touch-icon`, `apple-mobile-web-app-capable`, `apple-mobile-web-app-status-bar-style`, `apple-mobile-web-app-title` 추가. `description` meta도 보강.

### 4. 모바일 반응형

뷰포트 meta 이미 존재. 랜딩/로그인/`/app`/`/dashboard`가 모바일 폭에서 정상인지 재확인(Nav는 잔손질에서 정리됨). 필요 시 소규모 보정만.

## 오프라인 범위

앱 셸(빌드 JS/CSS/index.html) 프리캐시만. 오프라인에서 앱 로드는 되지만 데이터는 네트워크 필요(로그인/거래/대시보드는 온라인). 런타임 API 캐싱 없음.

## 테스트

- 빌드(`pnpm build`) 산출물에 `manifest.webmanifest` + 서비스워커(`sw.js`) + 아이콘이 생성되는지 확인.
- (선택) `dist/manifest.webmanifest` 파싱 스모크(name/icons 존재).
- 기존 45 vitest 회귀(플러그인 추가가 테스트 무영향인지).
- SW 등록/설치 가능성은 유닛 테스트 대상 아님 → build + 라이브(브라우저 설치/Lighthouse) 확인.

## 비목표 / 리스크

- 웹 푸시(범위 C), 런타임 데이터 오프라인 캐싱(범위 B), 오프라인 쓰기/동기화.
- 리스크: 아이콘 PNG 생성이 환경 rasterize에 의존 → 위 폴백 순서로 대응.
- SW 프리캐시가 코드 스플리팅 청크(대시보드 231KB 포함)까지 잡을 수 있음 — 앱 셸 오프라인 목적상 허용, 필요 시 glob 조정.
