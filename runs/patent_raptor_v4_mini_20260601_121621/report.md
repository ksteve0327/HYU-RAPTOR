# RAPTOR Patent V4-mini Report

V4-mini reuses the V3 tree/retrieval/reader outputs and recalculates open-ended Answer F1 against review-sheet gold reference answers.

## Core Metrics

- bm25_without_raptor: Answer F1=0.250, Answer Recall=0.297, Answer Precision=0.221, Source Recall=0.228, Judge pass aux=0.500
- bm25_with_raptor: Answer F1=0.405, Answer Recall=0.505, Answer Precision=0.351, Source Recall=0.980, Judge pass aux=0.900
- dense_bge_m3_without_raptor: Answer F1=0.430, Answer Recall=0.508, Answer Precision=0.381, Source Recall=0.750, Judge pass aux=0.900
- dense_bge_m3_with_raptor: Answer F1=0.428, Answer Recall=0.535, Answer Precision=0.377, Source Recall=1.000, Judge pass aux=0.800

## Gold QA

- QA 0 [global]: 신경망 시스템의 전력 효율을 높이기 위해 전압·클록 제어, 양자화, PIM/CIM 연산, 칩렛/NoC 스케줄링 기술을 함께 적용하면 어떤 종합 효과를 기대할 수 있는가?
- QA 1 [global]: 검색·질의응답 시스템에서 지식 그래프, 웹 콘텐츠 기반 답변 생성, 언어모델 문맥 압축, 이미지 코드 비교 기술을 결합하면 어떤 방식으로 응답 생성 효율을 높일 수 있는가?
- QA 2 [global]: 웨이퍼 공정 최적화 기술과 반도체 미세 구조·패키지 방열 기술은 반도체 제조 품질 개선에서 어떻게 상호 보완될 수 있는가?
- QA 3 [global]: 3차원 객체 인지, 이미지 분류, 동일 인물 이미지 검색 기술을 함께 고려할 때 비전 AI 시스템의 정확도와 처리 속도를 높이는 공통 전략은 무엇인가?
- QA 4 [global]: AI 가속기와 SoC/NoC 기반 집적회로에서 메모리 접근 제어, ECC 처리, 외부 트래픽 제어, DMA 및 PE 배열 기술을 함께 적용하는 목적은 무엇인가?
- QA 5 [local]: 15-615713 특허에서 온라인 소셜 네트워크 검색 결과의 순위는 어떤 기준으로 결정되나요?
- QA 6 [local]: 16-009456 특허에서 1차 신경망의 양자화 파라미터는 무엇이 생성하나요?
- QA 7 [local]: 16-245406 특허의 벡터 연산 회로에서 활성화 회로는 어떤 역할을 하나요?
- QA 8 [local]: 17-070786 특허에서 센서 데이터 분석 후 생성되는 이벤트의 목적은 무엇인가요?
- QA 9 [local]: 17-289227 특허에서 학습된 LSTM 신경망을 양자화할 때 각 게이트에 대해 어떤 행렬들이 목표 고정 비트폭으로 양자화되나요?
