# RAPTOR Patent Experiment Report

- Created: 2026-05-30T23:26:29
- Run label: v3
- Text column: 요약
- Sample size per category: 50
- Embedding backend: sentence-transformers
- Embedding model: BAAI/bge-m3
- Retrieval design: with_without_raptor
- QA mode: global_local
- QA count: 10
- Methods: bm25_without_raptor, bm25_with_raptor, dense_bge_m3_without_raptor, dense_bge_m3_with_raptor
- DPR backend: hf
- LLM model: gpt-5.5
- Reasoning: high
- LLM calls: 232
- Actual runtime: 1h 6m 2s
- Initial ETA: 3h 0m 0s
- Initial ETA absolute error: 1h 53m 57s

## Paper Metric Basis

RAPTOR 논문 메인 성능표는 retrieval recall이 아니라 task answer metric을 사용한다. QASPER는 Answer F1, QuALITY는 Accuracy, NarrativeQA는 ROUGE/BLEU/METEOR를 보고한다. 본 특허 QA는 QASPER처럼 open-ended answer 비교이므로 Answer F1을 메인 지표로 재측정하고, 같은 token-overlap 계산에서 나온 Answer Recall도 함께 표시했다.

## Paper Main - Answer F1

- bm25_with_raptor: 0.405
- bm25_without_raptor: 0.250
- dense_bge_m3_with_raptor: 0.428
- dense_bge_m3_without_raptor: 0.430

## Answer Recall

- bm25_with_raptor: 0.505
- bm25_without_raptor: 0.297
- dense_bge_m3_with_raptor: 0.535
- dense_bge_m3_without_raptor: 0.508

## Global vs Local Answer F1

- global / bm25_with_raptor: 0.399
- global / bm25_without_raptor: 0.289
- global / dense_bge_m3_with_raptor: 0.393
- global / dense_bge_m3_without_raptor: 0.292
- local / bm25_with_raptor: 0.411
- local / bm25_without_raptor: 0.211
- local / dense_bge_m3_with_raptor: 0.463
- local / dense_bge_m3_without_raptor: 0.568

## Global vs Local Answer Recall

- global / bm25_with_raptor: 0.530
- global / bm25_without_raptor: 0.340
- global / dense_bge_m3_with_raptor: 0.511
- global / dense_bge_m3_without_raptor: 0.369
- local / bm25_with_raptor: 0.480
- local / bm25_without_raptor: 0.255
- local / dense_bge_m3_with_raptor: 0.559
- local / dense_bge_m3_without_raptor: 0.648

## Auxiliary Judge Score

- bm25_with_raptor: 4.600
- bm25_without_raptor: 2.700
- dense_bge_m3_with_raptor: 4.700
- dense_bge_m3_without_raptor: 4.500

## Paper-style Main Performance


### Global QA

- bm25_with_raptor: Answer F1=0.399, Answer Recall=0.530, Accuracy=1.000, Avg Judge Score=4.800
- bm25_without_raptor: Answer F1=0.289, Answer Recall=0.340, Accuracy=0.800, Avg Judge Score=3.400
- dense_bge_m3_with_raptor: Answer F1=0.393, Answer Recall=0.511, Accuracy=0.800, Avg Judge Score=4.600
- dense_bge_m3_without_raptor: Answer F1=0.292, Answer Recall=0.369, Accuracy=0.800, Avg Judge Score=4.000

### Local QA

- bm25_with_raptor: Answer F1=0.411, Answer Recall=0.480, Accuracy=0.800, Avg Judge Score=4.400
- bm25_without_raptor: Answer F1=0.211, Answer Recall=0.255, Accuracy=0.200, Avg Judge Score=2.000
- dense_bge_m3_with_raptor: Answer F1=0.463, Answer Recall=0.559, Accuracy=0.800, Avg Judge Score=4.800
- dense_bge_m3_without_raptor: Answer F1=0.568, Answer Recall=0.648, Accuracy=1.000, Avg Judge Score=5.000

## With vs Without RAPTOR Delta

- BM25: answer_f1_delta=+0.155, answer_recall_delta=+0.207, accuracy_delta=+0.400, score_delta=+1.900 (10 QA)
- Dense BGE-M3: answer_f1_delta=-0.002, answer_recall_delta=+0.027, accuracy_delta=-0.100, score_delta=+0.200 (10 QA)

## Global vs Local Split Analysis

Global 5개, Local 5개만 사용한 pilot result이므로 통계적으로 충분한 표본은 아니다. 다만 Dense BGE-M3의 전체 평균 delta가 거의 0인 이유가 Global/Local 상쇄 때문인지 확인하는 데 중요한 진단 표다.
- BM25: global 0.289->0.399, local 0.211->0.411, all 0.250->0.405. Global과 Local 모두에서 RAPTOR all-node 검색이 Answer F1을 높였습니다.
- Dense BGE-M3: global 0.292->0.393, local 0.568->0.463, all 0.430->0.428. Global QA에서는 RAPTOR all-node가 상위 summary evidence를 보강했지만, Local QA에서는 특정 patent detail을 묻기 때문에 leaf-only 직접 검색이 더 강했습니다. 전체 평균은 이 상반된 효과를 가립니다.

## Best Method Selection Counts

- bm25_with_raptor: 4
- dense_bge_m3_with_raptor: 3
- dense_bge_m3_without_raptor: 3

## QA Best Method Summary

- QA 0 [global] best=dense_bge_m3_with_raptor; scores=bm25_with_raptor=5, bm25_without_raptor=4, dense_bge_m3_with_raptor=5, dense_bge_m3_without_raptor=4; reason=reference answer의 핵심 요소인 오류 허용 범위 기반 전압·클록 조정, 양자화·압축에 따른 모델/메모리/연산량 감소, PIM/CIM을 통한 데이터 이동 및 외부 메모리 접근 감소, 칩렛/NoC 기반 병렬 작업 분산 효과를 가장 균형 있게 포함한다. retrieved context에도 해당 요소들이 직접적으로 제시되어 근거성이 높다.
- QA 1 [global] best=bm25_with_raptor; scores=bm25_with_raptor=5, bm25_without_raptor=1, dense_bge_m3_with_raptor=4, dense_bge_m3_without_raptor=4; reason=reference answer의 핵심 요소인 지식 그래프 기반 후보 축소, 웹 콘텐츠 기반 리스트형 답변 생성, 문맥 압축을 통한 LLM 입력량 감소, 이미지 코드의 해밍 비교 가속을 모두 포함하고, retrieved context에도 해당 기술 묶음과 효과가 근거로 제시되어 있어 가장 충실하고 근거성이 높다.
- QA 2 [global] best=dense_bge_m3_with_raptor; scores=bm25_with_raptor=4, bm25_without_raptor=4, dense_bge_m3_with_raptor=5, dense_bge_m3_without_raptor=4; reason=reference answer의 핵심인 웨이퍼 공정 수율·결함 데이터 기반 최적 위치 및 척 유형 결정, 트렌치·리세스·절연막·소자 분리층·확산 차단 구조에 의한 미세 구조 품질 개선, 패키지 방열을 통한 열 신뢰성 확보를 가장 균형 있게 반영한다.
- QA 3 [global] best=bm25_with_raptor; scores=bm25_with_raptor=5, bm25_without_raptor=4, dense_bge_m3_with_raptor=4, dense_bge_m3_without_raptor=3; reason=reference answer의 핵심 요소인 컨텍스트 기반 객체 그룹/앵커 박스 선택, 프록시 모델과 비라벨링 데이터 샘플링, 얼굴 검출과 파레트 데이터 기반 동일 인물 검색, 이미지 코드의 해밍 비교를 메모리 근접 또는 메모리 컨트롤러에서 수행한다는 처리 가속 전략까지 모두 포함해 가장 완전하다.
- QA 4 [global] best=bm25_with_raptor; scores=bm25_with_raptor=5, bm25_without_raptor=4, dense_bge_m3_with_raptor=5, dense_bge_m3_without_raptor=5; reason=reference answer의 핵심 요소인 AI 가속기의 DMA/PE/시스톨릭 병렬화, 메모리 접근·데이터 이동 감소, ECC 기반 신뢰성, 외부 트래픽 제어에 따른 NoC 부하 감소, 라우팅·스케줄링 효율화를 가장 폭넓고 정확하게 반영하며 retrieved context도 이를 직접 뒷받침한다.
- QA 5 [local] best=dense_bge_m3_without_raptor; scores=bm25_with_raptor=5, bm25_without_raptor=1, dense_bge_m3_with_raptor=5, dense_bge_m3_without_raptor=5; reason=reference answer와 거의 동일하게 각 식별 객체별 3차원 텐서를 구성하고 그 텐서 기반 관련성 점수로 순위화한다고 답했으며, retrieved context도 해당 절차를 원문 수준으로 직접 뒷받침합니다.
- QA 6 [local] best=bm25_with_raptor; scores=bm25_with_raptor=5, bm25_without_raptor=1, dense_bge_m3_with_raptor=5, dense_bge_m3_without_raptor=5; reason=reference answer와 동일하게 2차 신경망 로직 회로가 1차 신경망의 양자화 파라미터를 생성한다고 답했고, retrieved context에도 해당 근거가 명시적으로 포함되어 있습니다.
- QA 7 [local] best=dense_bge_m3_without_raptor; scores=bm25_with_raptor=5, bm25_without_raptor=1, dense_bge_m3_with_raptor=4, dense_bge_m3_without_raptor=5; reason=reference answer와 거의 동일하게 활성화 회로가 누적값 벡터를 수신하고 각 누적값에 함수를 적용해 활성화값 벡터를 생성한다고 답했으며, retrieved context에도 해당 청구항 문구가 직접 포함되어 근거성이 가장 높습니다.
- QA 8 [local] best=dense_bge_m3_without_raptor; scores=bm25_with_raptor=2, bm25_without_raptor=2, dense_bge_m3_with_raptor=5, dense_bge_m3_without_raptor=5; reason=reference answer와 거의 동일하게, 센서 데이터 분석으로 결정된 구성 데이터가 식별한 각 동작을 수행하도록 이벤트가 생성되며, 이 이벤트가 해당 동작과 연관된 AI 모델 실행을 트리거한다는 핵심을 정확히 답했습니다. retrieved context에도 동일한 원문 근거가 직접 포함되어 있습니다.
- QA 9 [local] best=dense_bge_m3_with_raptor; scores=bm25_with_raptor=5, bm25_without_raptor=5, dense_bge_m3_with_raptor=5, dense_bge_m3_without_raptor=5; reason=답변이 reference answer와 정확히 일치하며, retrieved context에 게이트별 입력 가중치 행렬과 순환 가중치 행렬의 요소를 목표 고정 비트폭으로 양자화한다는 원문 근거가 직접 포함되어 있어 근거성이 가장 강합니다.

## Retrieval Hit Rate

- bm25_with_raptor: 0.890
- bm25_without_raptor: 0.885
- dense_bge_m3_with_raptor: 0.950
- dense_bge_m3_without_raptor: 0.935

## Appendix E Audit

- Repair log summaries: 40
- Unsupported claim rate before repair: 0.575
- Unsupported claim rate after repair: 0.000
- Audited summary nodes: 12
- Hallucination rate: 0.083

## BM25 Win Analysis

- QA 0 bm25_with_raptor: BM25 5 vs dense_bge_m3_with_raptor 5; terms: 전력(idf=3.34, score=4.07), 신경망(idf=2.42, score=3.21), pim/cim(idf=4.23, score=2.91), 클록(idf=4.23, score=2.91), 양자화(idf=3.13, score=2.84), 제어(idf=2.62, score=2.83)
- QA 1 bm25_with_raptor: BM25 5 vs dense_bge_m3_without_raptor 4; terms: 이미지(idf=3.61, score=5.91), 검색(idf=3.61, score=5.44), 그래프(idf=3.98, score=4.29), 지식(idf=3.78, score=4.07), 문맥(idf=4.23, score=3.83), 언어모델(idf=4.23, score=3.83)
- QA 3 bm25_with_raptor: BM25 5 vs dense_bge_m3_with_raptor 4; terms: 이미지(idf=3.61, score=5.91), 검색(idf=3.61, score=5.44), 객체(idf=3.47, score=4.61), ai(idf=2.81, score=4.00), 3차원(idf=3.47, score=3.74), 분류(idf=3.61, score=3.27)
- QA 4 bm25_with_raptor: BM25 5 vs dense_bge_m3_without_raptor 5; terms: ai(idf=2.81, score=4.00), 메모리(idf=1.94, score=3.65), dma(idf=3.34, score=3.60), 처리(idf=2.07, score=3.11), 제어(idf=2.62, score=2.83), pe(idf=3.98, score=2.73)
- QA 5 bm25_with_raptor: BM25 5 vs dense_bge_m3_without_raptor 5; terms: 검색(idf=3.61, score=6.10), 결과의(idf=4.57, score=3.36)
- QA 6 bm25_with_raptor: BM25 5 vs dense_bge_m3_without_raptor 5; terms: 1차(idf=5.08, score=6.72), 양자화(idf=3.13, score=4.92)
- QA 7 bm25_with_raptor: BM25 5 vs dense_bge_m3_without_raptor 5; terms: 벡터(idf=3.13, score=3.28), 연산(idf=2.46, score=3.20), 활성화(idf=4.57, score=3.03), 회로는(idf=3.98, score=2.64)
- QA 9 bm25_without_raptor: BM25 5 vs dense_bge_m3_without_raptor 5; terms: lstm(idf=4.90, score=9.85)

## Why BM25 Remains Competitive on Patent Data

특허 문서는 소설이나 일반 서술형 문서와 달리 핵심 단어가 기술 구성요소의 정확한 식별자처럼 작동한다. GEMM, DDR, GaN, 부동 게이트, 정규화 회로, PMOS 트랜지스터 같은 표현은 바꿔 쓰기보다 그대로 유지되는 경우가 많다.
- 전문 용어의 희소성: 특정 기술어의 document frequency가 낮아 IDF가 커지고, 질문과 문서가 같은 희귀 용어를 공유하면 관련 특허가 상위로 올라간다.
- 구성요소 명칭의 반복: 특허 요약은 핵심 부품과 동작을 반복적으로 설명해 term frequency가 높아진다.
- 표현의 정밀성: 기술 용어는 문학적 표현처럼 자유롭게 치환되지 않아 exact-match가 dense retrieval보다 직접적인 검색 신호가 되는 경우가 있다.
따라서 본 실험 결과는 RAPTOR가 모든 검색 지표에서 BM25를 압도했다기보다, BM25는 특허의 precise lexical retrieval에 강하고 with-RAPTOR 전체 node 검색은 최종 QA 답변 생성에 필요한 summary evidence를 보강하는 상보적 관계로 해석하는 것이 적절하다.

## Qualitative Samples

### QA 0 [global] - bm25_without_raptor

Question: 신경망 시스템의 전력 효율을 높이기 위해 전압·클록 제어, 양자화, PIM/CIM 연산, 칩렛/NoC 스케줄링 기술을 함께 적용하면 어떤 종합 효과를 기대할 수 있는가?

Best method: dense_bge_m3_with_raptor

Answer: 제공된 문맥만으로는 전압·클록 제어 및 칩렛/NoC 스케줄링까지 함께 적용했을 때의 효과를 구체적으로 판단하기에는 부족합니다.

다만 문맥에 근거해 말할 수 있는 종합 효과는 다음과 같습니다. 양자화를 통해 가중치 데이터 값의 수를 줄이면 신경망 연산에 필요한 데이터량과 연산 복잡도를 낮출 수 있습니다. PIM 연산을 적용하면 메모리 내부에서 팝 카운트, 논리 비트 연산, 데이터 연산 등을 수행하여 CPU와 메모리 사이의 데이터 전송을 줄이고, 메모리 트래픽과 에너지 소모를 개선할 수 있습니다. 또한 NPU 스케줄러가 신경망 구조 데이터나 데이터 지역성 정보를 기반으로 프로세싱 엘리먼트 어레이와 메모리 시스템을 제어하면 연산 및 메모리 사용 효율을 높일 수 있습니다.

따라서 문맥상 기대 가능한 효과는 데이터 이동 감소, 메모리 트래픽 개선, 연산 효율 향상, CPU 부담 감소, 시스템 성능 및 에너지 효율 개선입니다. 전압·클록 제어와 칩렛/NoC 스케줄링의 구체적 효과는 제공된 문맥만으로는 불충분합니다.

Score: 4

Context preview: 본 발명의 일 실시 예에 따른 가중치 데이터 처리 방법은 하드웨어 기반의 인공 신경망 연산을 수행하기 위한 장치를 구현하기 위해 가중치 데이터 값의 수를 줄이는 가중치 데이터 처리 방법으로, 가중치 데이터 내의 가중치 값의 범위를 복수의 구간으로 나누어 가중치 레벨에 대응시켜 양자화 시킨 레벨링(leveling) 가중치 데이터를 생성할 수 있도록 처리한 가중치 데이터 처리 방법 및 장치와 상기 가중치 데이터를 통해 구현된 인공 신경망 연산을 수행하는 장치를 제공한다.  본 발명은 PIM 컴퓨팅 시스템 및 그의 메모리 컨트롤러를 개시하며, 상기 PIM 컴퓨팅 시스템은 PIM 리퀘스트의 경우 페이지 단위로 PIM 연산을 수행할 수 있도록 버스트 렝쓰를 증가시킴으로써 메모리 트래픽을 개선하고 PIM 연산 효율을 개선할 수 있다.  신경망 모델을 이용한 뉴로모픽 컴퓨팅 시스템의 운영체제 구성 방법 및 이를 위한 장치가 개시된다. 본 발명의 일실시예에 따른 뉴로모픽 컴퓨팅 시스템의 운영체제 구성 방법은 뉴로모픽 컴퓨팅 시스템에 상응하는 운영체제 구성요소를 식별하는 단계; 상기 운영체제 구성요소를 고려하여 신경망 모델 형태의 운영체제를 구성하는 단계; 및 상기 신경망 모델 형태의 운영체제를 상기 뉴로모픽 컴퓨팅 시스템에 탑재하고, 상기 신경망 모델 형태의 운영체제를 통해 상기 뉴로모픽 컴퓨팅 시스템의 전체 또는 일부 기능을 관리 및 운용하는 단계를 포함한다.  일 측면에 따른 뉴럴 네트워크 장치에서 연산을 수행하는 방법은, 적어도 하나의 입력 피처맵 및 적어도 하나의 커널을 포함하는 복수의 연산 그룹들과, 복수의 연산 그룹들 각각에 대응하는 태그(tag) 정보를 획득하고, 복수의 연산 유닛들 중 유휴 상태인 연산 유닛을 결정할 수 있다.  유휴 상태인 연산 유닛에서, 복수의 연산 그룹들 중 소정의 연산 그룹에 포함된 입력 피처맵 및 커널 간의 컨벌루션 연산을 수행함으로써 중간 피처맵을 생성하고, 소정의 연산 그룹에 대응하는 태그 정보에 기초하여 복수의 후처리 유닛들 중 상기 태그 정보에 대응하는 후처리 유닛을 결정할 수 있다. 후처리 유닛에서, 적어도 하나의 중간 피처맵을 이용하여 출력 피처맵을 생성할 수 있다.  가속기가 개시된다. 하드웨어는 데이터베이스에 대한 쿼리를 처리할 수 있다. 저장소는 데이터베이스에서 쿼리를 처리하는 소프트웨어를 저장할 수 있다. 코디네이터는 데이터베이스에 대한 쿼리의 결과를 생성하기 위해 쿼

### QA 0 [global] - bm25_with_raptor

Question: 신경망 시스템의 전력 효율을 높이기 위해 전압·클록 제어, 양자화, PIM/CIM 연산, 칩렛/NoC 스케줄링 기술을 함께 적용하면 어떤 종합 효과를 기대할 수 있는가?

Best method: dense_bge_m3_with_raptor

Answer: 전압·클록 제어, 양자화, PIM/CIM 연산, 칩렛/NoC 스케줄링을 함께 적용하면 신경망 시스템 전반에서 전력 효율과 처리 성능을 동시에 높이는 효과를 기대할 수 있다.

구체적으로는 오류 허용 범위 안에서 전압과 클록을 조정해 불필요한 전력 소모를 줄이고, 양자화·압축으로 모델 크기, 메모리 사용량, 데이터 경로 대역폭, 추론 연산량을 줄일 수 있다. 또한 PIM/CIM 연산을 통해 메모리 내부 또는 근접 위치에서 연산을 수행함으로써 데이터 이동과 외부 메모리 접근을 줄이고 병렬 처리 성능을 높일 수 있다.

여기에 칩렛 및 NoC 기반 스케줄링을 결합하면 레인, 가속기, 메모리, 칩렛 간 작업 분산과 라우팅을 효율적으로 제어할 수 있다. 결과적으로 신경망 실행 시 전력 소모, 메모리 트래픽, 연산량, 데이터 이동량을 줄이면서 처리량과 시스템 활용도를 개선하는 종합 효과를 기대할 수 있다.

Score: 5

Context preview: 이 특허 묶음은 AI·신경망 처리, 메모리 중심 연산, 반도체 패키징, 검색·질의응답, 영상·이미지 처리, SoC/NoC 제어 기술을 포괄한다.  **핵심 기술**  - 신경망 실행 결과의 오류율을 비교해 전압·클록 등 전력 설정을 조정하는 전력 관리 기술 - 신경망 파라미터 양자화, 바이너리 뉴럴넷 학습, 모델 압축, LSTM·AI 프로세서 데이터 경로 양자화 기술 - VPU, SIMD, DMA 시퀀서, GEMM·컨볼루션 버퍼링, 시스톨릭 어레이, PE 배열 등 신경망 가속기 구조 - PIM/CIM 기반 메모리 내부 또는 인접 연산, 메모리 요청 스케줄링, 온칩 데이터 이동 제어 기술 - 3D/2.5D 패키징, 칩렛, 메모리 다이·로직 다이 결합, 인터포저 및 열 관리 구조 - 검색 질의 관련도 산정, 센서 데이터 분류, 지식 그래프 생성, 웹 콘텐츠 기반 답변 생성, 언어모델 문맥 압축 기술 - 웨이퍼 공정 수율·결함 데이터를 이용한 최적 위치 결정 및 척 유형 결정 기술 - 포인트 클라우드 기반 3차원 객체 인지 모델을 영상 컨텍스트와 객체 클래스별 앵커 박스에 맞게 학습하는 기술 - 이미지 분류용 프록시 모델 학습, 동일 인물 이미지 검색, 이미지 코드의 해밍 비교 처리 기술 - ASIC/SoC/NoC에서 암호화폐 채굴, 외부 트래픽 제어, ECC 처리, NoC 라우팅, 자율주행차용 칩렛 워크로드 스케줄링, ML 가속기 구성을 수행하는 기술  **목적**  - 허용 가능한 오류 범위 내에서 신경망 전력 효율을 높이는 것 - 모델 크기, 메모리 사용량, 데이터 이동량, 연산량을 줄이는 것 - 메모리 내부 연산과 병렬 처리를 통해 AI·그래픽·데이터베이스·머신러닝 작업을 가속하는 것 - 멀티레인 AI 시스템, DMA, 메모리 접근, 칩렛 간 작업 분산을 효율적으로 제어하는 것 - 영상 생성·복원, 객체 인지, 이미지 검색 및 이미지 코드 비교 성능을 높이는 것 - 검색·질의응답·지식 그래프·언어모델 입력 처리에서 관련 정보 추출과 응답 생성을 효율화하는 것 - 반도체 공정, 웨이퍼 위치, 패키지 구조, 메모리 신뢰성 및 열 특성을 개선하는 것  **주요 구성 요소**  - 오류율 산정 절차, 애플리케이션 오류 허용치, 전압·클록 제어부 - 레인별 오케스트레이터, 상위 오케스트레이터, 활성 컴포넌트 제어 구조 - VPU 데이터 경로, SIMD 레인, min/max 수집기, DMA 시퀀서, 로드·스토어·퍼뮤트

### QA 0 [global] - dense_bge_m3_without_raptor

Question: 신경망 시스템의 전력 효율을 높이기 위해 전압·클록 제어, 양자화, PIM/CIM 연산, 칩렛/NoC 스케줄링 기술을 함께 적용하면 어떤 종합 효과를 기대할 수 있는가?

Best method: dense_bge_m3_with_raptor

Answer: 제공된 문맥만으로는 “전압·클록 제어”의 효과까지는 판단하기에 불충분합니다.

다만 문맥에 나온 기술들을 함께 보면, 양자화는 비트 수를 줄여 메모리 사용량과 데이터 경로 대역폭을 크게 낮출 수 있고, PIM/CIM 연산은 메모리 근처 또는 메모리 내부에서 연산을 수행해 메모리 트래픽과 연산 효율을 개선할 수 있습니다. 또한 칩렛/3D 적층 구조와 NoC 기반 구성, NPU 스케줄링은 높은 메모리 대역폭, 낮은 전력 소모, 작은 폼팩터, 데이터 지역성 기반 제어를 기대하게 합니다.

따라서 종합적으로는 메모리 접근량과 데이터 이동 비용 감소, 대역폭 효율 향상, GEMM/신경망 연산 처리량 증가, PIM/CIM 기반 연산 효율 향상, 그리고 전체 AI 처리 시스템의 전력 효율 개선을 기대할 수 있습니다. 다만 전압·클록 제어와의 결합 효과는 문맥에 직접 근거가 없습니다.

Score: 4

Context preview: A chiplet-based architecture may quantize, or reduce, the number of bits at various stages of the data path in an artificial-intelligence processor. This architecture may leverage the synergy between quantizing multiple dimensions together to greatly decrease the memory usage and data path bandwidth. Internal weights may be quantized statically after a training procedure. Accumulator bits and activation bits may be quantized dynamically during an inference operation. New hardware logic may be configured to quantize the outputs of each operation directly from the core or other processing node before the tensor is stored in memory. Quantization may use a statistic from a previous tensor for a current output tensor, while also calculating a statistic to be used on a subsequent output tensor. In addition to quantizing based on a statistic, bits can be further quantized using a Kth percentile clamping operation.  Devices and methods related to spiking neural units in memory. One device includes a memory array and a complementary metal-oxide semiconductor (CMOS) coupled to the memory array and located under the memory array, wherein the CMOS includes a spiking neural unit comprising logi

### QA 0 [global] - dense_bge_m3_with_raptor

Question: 신경망 시스템의 전력 효율을 높이기 위해 전압·클록 제어, 양자화, PIM/CIM 연산, 칩렛/NoC 스케줄링 기술을 함께 적용하면 어떤 종합 효과를 기대할 수 있는가?

Best method: dense_bge_m3_with_raptor

Answer: 전압·클록 제어, 양자화, PIM/CIM 연산, 칩렛/NoC 스케줄링을 함께 적용하면 신경망 시스템 전반에서 다음과 같은 종합 효과를 기대할 수 있다.

허용 가능한 오류 범위 안에서 전압과 클록을 조정해 불필요한 전력 소모를 줄이고, 양자화·압축·희소성 활용으로 모델 크기, 메모리 사용량, 대역폭, 추론 연산량을 줄일 수 있다. 또한 PIM/CIM 기반 메모리 내부 또는 인접 연산을 통해 CPU와 메모리 사이의 데이터 이동 및 외부 메모리 접근을 줄여 에너지 효율과 처리 성능을 높일 수 있다.

여기에 칩렛 및 NoC 스케줄링을 결합하면 여러 ML 가속 코어, GPU 칩렛, 센서 입력 칩렛, 캐시 메모리, NoC 라우팅 자원을 효율적으로 분산 제어할 수 있어 병렬 처리 효율이 증가한다. 결과적으로 신경망 연산의 전력 효율, 메모리 대역폭 효율, 데이터 이동 효율, 작업 분산 효율이 함께 개선되고, 고성능·저전력 신경망 처리 시스템 구현이 가능해진다.

Score: 5

Context preview: 이 특허 묶음은 AI·신경망 처리, 메모리 중심 연산, 반도체 패키징, 검색·질의응답, 영상·이미지 처리, SoC/NoC 제어 기술을 포괄한다.  **핵심 기술**  - 신경망 실행 결과의 오류율을 비교해 전압·클록 등 전력 설정을 조정하는 전력 관리 기술 - 신경망 파라미터 양자화, 바이너리 뉴럴넷 학습, 모델 압축, LSTM·AI 프로세서 데이터 경로 양자화 기술 - VPU, SIMD, DMA 시퀀서, GEMM·컨볼루션 버퍼링, 시스톨릭 어레이, PE 배열 등 신경망 가속기 구조 - PIM/CIM 기반 메모리 내부 또는 인접 연산, 메모리 요청 스케줄링, 온칩 데이터 이동 제어 기술 - 3D/2.5D 패키징, 칩렛, 메모리 다이·로직 다이 결합, 인터포저 및 열 관리 구조 - 검색 질의 관련도 산정, 센서 데이터 분류, 지식 그래프 생성, 웹 콘텐츠 기반 답변 생성, 언어모델 문맥 압축 기술 - 웨이퍼 공정 수율·결함 데이터를 이용한 최적 위치 결정 및 척 유형 결정 기술 - 포인트 클라우드 기반 3차원 객체 인지 모델을 영상 컨텍스트와 객체 클래스별 앵커 박스에 맞게 학습하는 기술 - 이미지 분류용 프록시 모델 학습, 동일 인물 이미지 검색, 이미지 코드의 해밍 비교 처리 기술 - ASIC/SoC/NoC에서 암호화폐 채굴, 외부 트래픽 제어, ECC 처리, NoC 라우팅, 자율주행차용 칩렛 워크로드 스케줄링, ML 가속기 구성을 수행하는 기술  **목적**  - 허용 가능한 오류 범위 내에서 신경망 전력 효율을 높이는 것 - 모델 크기, 메모리 사용량, 데이터 이동량, 연산량을 줄이는 것 - 메모리 내부 연산과 병렬 처리를 통해 AI·그래픽·데이터베이스·머신러닝 작업을 가속하는 것 - 멀티레인 AI 시스템, DMA, 메모리 접근, 칩렛 간 작업 분산을 효율적으로 제어하는 것 - 영상 생성·복원, 객체 인지, 이미지 검색 및 이미지 코드 비교 성능을 높이는 것 - 검색·질의응답·지식 그래프·언어모델 입력 처리에서 관련 정보 추출과 응답 생성을 효율화하는 것 - 반도체 공정, 웨이퍼 위치, 패키지 구조, 메모리 신뢰성 및 열 특성을 개선하는 것  **주요 구성 요소**  - 오류율 산정 절차, 애플리케이션 오류 허용치, 전압·클록 제어부 - 레인별 오케스트레이터, 상위 오케스트레이터, 활성 컴포넌트 제어 구조 - VPU 데이터 경로, SIMD 레인, min/max 수집기, DMA 시퀀서, 로드·스토어·퍼뮤트

### QA 1 [global] - bm25_without_raptor

Question: 검색·질의응답 시스템에서 지식 그래프, 웹 콘텐츠 기반 답변 생성, 언어모델 문맥 압축, 이미지 코드 비교 기술을 결합하면 어떤 방식으로 응답 생성 효율을 높일 수 있는가?

Best method: bm25_with_raptor

Answer: 제공된 문맥만으로는 답변하기에 불충분합니다.

문맥에는 얼굴 데이터/파레트 데이터 비교를 통한 이미지 검색, 프록시 모델 학습, 모델 국부 압축, NPU/PIM/GPU 최적화 등은 언급되어 있지만, 검색·질의응답 시스템에서 지식 그래프, 웹 콘텐츠 기반 답변 생성, 언어모델 문맥 압축, 이미지 코드 비교 기술을 결합하여 응답 생성 효율을 높이는 구체적 방식은 설명되어 있지 않습니다.

Score: 1

Context preview: 일 실시예에 따른 동일한 인물이 포함된 이미지를 검색하기 위한 이미지 처리 시스템은, 이미지 데이터가 저장되는 제1 저장 모듈, 검색 대상이 되는 인물이 포함된 입력 데이터를 입력 받는 입력 모듈, 상기 이미지 데이터에 포함된 얼굴 영역을 추출하여 얼굴 데이터를 생성하는 얼굴 검출 모듈, 적어도 하나의 상기 얼굴 데이터를 포함하는 파레트 데이터를 생성하는 파레트 데이터 생성 모듈, 및 상기 입력 데이터 및 상기 파레트 데이터를 비교하여 생성된 결과 정보를 기반으로 상기 입력 데이터와 동일한 인물이 포함된 상기 이미지 데이터를 출력하는 이미지 출력 모듈을 포함하는 이미지 처리 장치;를 포함할 수 있다.  본 발명은 이미지 분류 장치에 의해 수행되는 방법에 있어서, 이미지 분류가 필요한 이미지 데이터를 획득하는 단계, 이미지 데이터에서 라벨링 데이터 및 비 라벨링 데이터로 분류하는 단계, 라벨링 데이터 중 일부를 활용하여 프록시 모델을 학습하는 단계, 비 라벨링 데이터 중 샘플링 처리를 통해 비 라벨링 데이터를 분류하는 단계, 및 분류된 비 라벨링 데이터 중 일부 데이터를 프록시 모델에 입력하여 학습하는 단계를 포함하는 비전 기반 산업 응용 프로그램에서 프록시 모델을 활용한 라벨링 데이터를 획득하는 방법 및 그 장치에 관한 것이다.  본 발명은 PIM 컴퓨팅 시스템 및 그의 메모리 컨트롤러를 개시하며, 상기 PIM 컴퓨팅 시스템은 PIM 리퀘스트의 경우 페이지 단위로 PIM 연산을 수행할 수 있도록 버스트 렝쓰를 증가시킴으로써 메모리 트래픽을 개선하고 PIM 연산 효율을 개선할 수 있다.  인공지능 모델의 국부 압축 방법 및 시스템을 개시한다. 일실시예에 따른 모델 국부 압축 방법은 사전 학습된 모델을 입력받는 단계, 상기 입력받은 모델의 일부로서의 레이어 그룹을 선정하는 단계 및 상기 적어도 하나의 프로세서에 의해, 상기 선정된 레이어 그룹을 부분적으로 압축하고, 상기 압축된 레이어 그룹에 대한 재학습을 수행하는 단계를 포함하되, 상기 압축된 레이어 그룹에 대한 재학습은, 상기 선정된 레이어 그룹에 대해 미리 저장된 입력 데이터 및 출력 데이터에 기반하여 상기 압축된 레이어 그룹을 재학습하는 것을 포함할 수 있다.  본 발명은 병렬 프로세서에 관한 것이다. 본 발명의 병렬 프로세서는 행들 및 열들로 배열되는 복수의 프로세싱 소자들을 포함하는 프로세싱 소자 어레이, 프로세싱 소자들의 행들에 대응하는 행 메모리들을

### QA 1 [global] - bm25_with_raptor

Question: 검색·질의응답 시스템에서 지식 그래프, 웹 콘텐츠 기반 답변 생성, 언어모델 문맥 압축, 이미지 코드 비교 기술을 결합하면 어떤 방식으로 응답 생성 효율을 높일 수 있는가?

Best method: bm25_with_raptor

Answer: 제공된 맥락상, 네 기술을 결합하면 **응답 생성 전에 관련 후보를 줄이고, 입력 문맥을 압축하며, 이미지 매칭 처리를 메모리 근접에서 수행하는 방식**으로 효율을 높일 수 있다.

검색 질의가 들어오면 먼저 지식 그래프에서 노드 임베딩을 이진 임베딩 벡터로 변환하고 질의 관련 노드를 선택해 응답 후보 범위를 좁힌다. 이후 검색엔진이 관련 있다고 판단한 웹페이지 콘텐츠를 딥러닝 모델에 입력해 헤더와 목록 요소를 포함한 리스트형 답변을 생성할 수 있다.

그 다음 후보 문맥 중 목표 문맥을 선택하고 일부 정보를 압축해 언어모델용 프롬프트 정보를 구성하면, 언어모델에 제출되는 콘텐츠 단위가 줄어 처리 자원과 시간이 절감된다.

이미지 코드 비교가 필요한 경우에는 이미지의 이진 임베딩 등 이미지 코드를 메모리 시스템 또는 메모리 컨트롤러에서 해밍 처리로 비교해 매칭 여부를 빠르게 식별할 수 있다. 이는 이미지 데이터셋 처리 속도와 처리량을 높이고, 응답 생성 과정에서 필요한 시각 정보 후보를 효율적으로 줄이는 데 기여한다.

따라서 전체적으로는 **지식 그래프 기반 후보 축소, 웹 콘텐츠 기반 답변 생성, 문맥 압축을 통한 프롬프트 입력량 감소, 해밍 기반 이미지 코드 비교 가속**을 통해 응답 생성의 계산량, 데이터 이동량, 처리 시간과 자원 사용을 줄일 수 있다.

Score: 5

Context preview: 이 특허 묶음은 AI·신경망 처리, 메모리 중심 연산, 반도체 패키징, 검색·질의응답, 영상·이미지 처리, SoC/NoC 제어 기술을 포괄한다.  **핵심 기술**  - 신경망 실행 결과의 오류율을 비교해 전압·클록 등 전력 설정을 조정하는 전력 관리 기술 - 신경망 파라미터 양자화, 바이너리 뉴럴넷 학습, 모델 압축, LSTM·AI 프로세서 데이터 경로 양자화 기술 - VPU, SIMD, DMA 시퀀서, GEMM·컨볼루션 버퍼링, 시스톨릭 어레이, PE 배열 등 신경망 가속기 구조 - PIM/CIM 기반 메모리 내부 또는 인접 연산, 메모리 요청 스케줄링, 온칩 데이터 이동 제어 기술 - 3D/2.5D 패키징, 칩렛, 메모리 다이·로직 다이 결합, 인터포저 및 열 관리 구조 - 검색 질의 관련도 산정, 센서 데이터 분류, 지식 그래프 생성, 웹 콘텐츠 기반 답변 생성, 언어모델 문맥 압축 기술 - 웨이퍼 공정 수율·결함 데이터를 이용한 최적 위치 결정 및 척 유형 결정 기술 - 포인트 클라우드 기반 3차원 객체 인지 모델을 영상 컨텍스트와 객체 클래스별 앵커 박스에 맞게 학습하는 기술 - 이미지 분류용 프록시 모델 학습, 동일 인물 이미지 검색, 이미지 코드의 해밍 비교 처리 기술 - ASIC/SoC/NoC에서 암호화폐 채굴, 외부 트래픽 제어, ECC 처리, NoC 라우팅, 자율주행차용 칩렛 워크로드 스케줄링, ML 가속기 구성을 수행하는 기술  **목적**  - 허용 가능한 오류 범위 내에서 신경망 전력 효율을 높이는 것 - 모델 크기, 메모리 사용량, 데이터 이동량, 연산량을 줄이는 것 - 메모리 내부 연산과 병렬 처리를 통해 AI·그래픽·데이터베이스·머신러닝 작업을 가속하는 것 - 멀티레인 AI 시스템, DMA, 메모리 접근, 칩렛 간 작업 분산을 효율적으로 제어하는 것 - 영상 생성·복원, 객체 인지, 이미지 검색 및 이미지 코드 비교 성능을 높이는 것 - 검색·질의응답·지식 그래프·언어모델 입력 처리에서 관련 정보 추출과 응답 생성을 효율화하는 것 - 반도체 공정, 웨이퍼 위치, 패키지 구조, 메모리 신뢰성 및 열 특성을 개선하는 것  **주요 구성 요소**  - 오류율 산정 절차, 애플리케이션 오류 허용치, 전압·클록 제어부 - 레인별 오케스트레이터, 상위 오케스트레이터, 활성 컴포넌트 제어 구조 - VPU 데이터 경로, SIMD 레인, min/max 수집기, DMA 시퀀서, 로드·스토어·퍼뮤트

### QA 1 [global] - dense_bge_m3_without_raptor

Question: 검색·질의응답 시스템에서 지식 그래프, 웹 콘텐츠 기반 답변 생성, 언어모델 문맥 압축, 이미지 코드 비교 기술을 결합하면 어떤 방식으로 응답 생성 효율을 높일 수 있는가?

Best method: bm25_with_raptor

Answer: 지식 그래프, 웹 콘텐츠 기반 답변 생성, 언어모델 문맥 압축, 이미지 코드 비교 기술을 결합하면 다음과 같이 응답 생성 효율을 높일 수 있다.

검색 질의가 입력되면 먼저 웹페이지 콘텐츠 중 검색엔진이 관련 있다고 판단한 내용을 이용해 답변 후보를 구성할 수 있다. 이 과정에서 지식 그래프는 입력 텍스트로부터 생성된 엔티티 노드와 이들을 연결하는 엣지를 통해 질의와 관련된 핵심 대상 및 관계를 구조화한다.

그 다음, 후보 문맥 전체를 그대로 언어모델에 넣는 대신, 입력 질의와 후보 문맥 정보 중 필요한 부분만 선택하고, source information의 content unit 수를 줄이는 방식으로 프롬프트를 압축한다. 이렇게 하면 언어모델에 제출되는 문맥량이 감소하여 처리 자원과 시간이 줄어든다.

또한 지식 그래프 노드의 임베딩을 이진 임베딩 벡터로 변환해 질의와 빠르게 비교하거나, 이미지 검색이 필요한 경우 이미지 코드를 binary embedding으로 표현하고 Hamming processing을 통해 가까운 메모리 장치 또는 메모리 컨트롤러에서 비교할 수 있다. 이는 대규모 데이터셋에서 유사 항목 검색 속도를 높인다.

결과적으로 시스템은 웹 콘텐츠에서 답변 후보를 만들고, 지식 그래프로 관련 정보를 구조화하며, 압축된 문맥만 언어모델에 전달하고, 이진 임베딩 기반 비교로 검색 후보를 빠르게 좁힘으로써 응답 생성에 필요한 연산량, 문맥 처리량, 검색 시간을 줄일 수 있다.

Score: 4

Context preview: Various technologies relating to constructing an answer to a query are described herein, wherein the answer is in list form. The answer includes a header and a list element. A deep model receives content of a webpage that is deemed relevant to the query by a search engine and constructs the answer to the webpage upon receipt of the query.  A technique for interacting with a machine-trained language model uses dynamic prompt management. The technique includes: receiving an input query and creating prompt information that expresses the input query and targeted context information. The targeted context information is selected from candidate context information. Further, a part of the prompt information is formed by compressing source information by reducing a number of content units in the source information (where the source information includes the input query and/or the candidate context information). The method further includes submitting the prompt information to the machine-trained language model, and receiving a response from the machine-trained language model based on the prompt information. The technique has the overall effect of reducing the number of content units submitted

### QA 1 [global] - dense_bge_m3_with_raptor

Question: 검색·질의응답 시스템에서 지식 그래프, 웹 콘텐츠 기반 답변 생성, 언어모델 문맥 압축, 이미지 코드 비교 기술을 결합하면 어떤 방식으로 응답 생성 효율을 높일 수 있는가?

Best method: bm25_with_raptor

Answer: 검색·질의응답 시스템에서 이 기술들을 결합하면, 응답 생성 효율은 다음 방식으로 높아질 수 있다.

먼저 지식 그래프를 이용해 자연어 입력에서 생성된 엔티티 노드와 엣지 중 질의와 관련된 노드를 식별한다. 이때 노드 임베딩을 이진 임베딩 벡터로 변환하고 질의와 평가하여 관련 노드만 선택하면, 전체 지식 그래프를 탐색하지 않고 응답에 필요한 지식만 빠르게 추출할 수 있다.

그 다음 검색엔진이 관련 있다고 판단한 웹페이지 콘텐츠를 딥러닝 모델에 입력해 헤더와 목록 요소를 포함하는 리스트형 답변을 생성할 수 있다. 이는 웹 콘텐츠에서 답변 구조를 직접 구성하므로, 질의응답 결과를 사용자가 이해하기 쉬운 형식으로 빠르게 제공하는 데 기여한다.

또한 입력 질의와 후보 문맥 정보 중 목표 문맥을 선택하고, 일부 정보를 압축해 언어모델에 제출할 프롬프트 정보를 구성하면 언어모델에 입력되는 콘텐츠 단위 수가 줄어든다. 그 결과 언어모델이 처리해야 할 입력량이 감소하여 처리 자원과 시간이 절감된다.

이미지 코드 비교 기술은 이미지의 이진 임베딩 등 이미지 코드를 해밍 처리 유닛이나 메모리 컨트롤러에서 비교함으로써, 이미지 데이터셋과의 매칭 또는 신경망 결과 식별을 메모리 장치에 가까운 위치에서 빠르게 수행하게 한다. 따라서 질의응답 시스템이 이미지 기반 정보까지 활용하는 경우, 관련 이미지 후보를 빠르게 선별해 응답 생성에 필요한 데이터 처리량을 줄일 수 있다.

결과적으로 지식 그래프는 관련 지식 노드를 좁히고, 웹 콘텐츠 기반 모델은 구조화된 답변을 만들며, 문맥 압축은 언어모델 입력량을 줄이고, 이미지 코드 비교는 이미지 관련 후보 탐색을 빠르게 처리한다. 이 조합은 응답 생성에 필요한 검색·선별·입력 처리 부담을 줄여 전체 응답 생성 효율을 높일 수 있다.

Score: 4

Context preview: 이 특허 묶음은 AI를 활용해 검색 질의, 센서 데이터, 자연어 텍스트, 지식 그래프, 웹 콘텐츠, 질의응답 후보, 언어모델 입력 문맥에서 관련 정보를 추출·평가·응답하는 기술에 관한 것이다.  핵심 기술은 검색 질의와 객체 간 매칭 행렬을 3차원 텐서로 구성해 객체 관련도 점수를 산출하고 검색 결과를 순위화하는 기술, 감지 장치 내에서 센서 데이터를 분석해 실행 동작과 대응 AI 모델을 결정하고 데이터를 분류하는 기술, 사전학습 언어모델로 자연어 입력에서 엔티티 노드와 엣지를 생성해 지식 그래프를 구축하는 기술이다.  또한 지식 그래프 노드의 임베딩을 이진 임베딩 벡터로 변환해 질의 관련 노드를 선택하고 응답을 제공하는 기술, 웹페이지 콘텐츠를 딥러닝 모델에 입력해 헤더와 목록 요소를 포함한 리스트형 답변을 생성하는 기술, 질문과 후보 답변의 문장 길이에 따라 BiLSTM 또는 Transformer 특징 추출기를 선택하고 어텐션 풀링으로 상관도를 측정하는 답변 선택 기술, 후보 문맥 중 목표 문맥을 선택·압축해 언어모델용 프롬프트 정보를 구성하는 기술을 포함한다.  주요 구성 요소는 클라이언트 시스템, 검색 질의, 매칭 행렬, 3차원 텐서, 관련도 점수, 센서 장치, 구성 데이터, 이벤트, AI 모델, 사전학습 언어모델, 지식 그래프의 노드와 엣지, 이진 임베딩 벡터, 딥러닝 모델, 웹페이지 콘텐츠, 계층적 길이 적응형 신경망, BiLSTM, Transformer, 어텐션 풀링, 입력 질의, 후보·목표 문맥 정보 및 프롬프트 정보이다.  효과는 검색 결과의 관련도 기반 순위화, 장치 내 센서 데이터 분석 및 AI 모델 기반 분류, 자연어 기반 지식 그래프 생성, 질의 관련 지식 그래프 노드 식별, 웹 콘텐츠 기반 답변 생성, 질문-답변 상관도 평가, 언어모델 입력량 감소를 통한 처리 자원과 시간 절감이다.  이 특허 묶음은 검색, 질의응답, 지식 그래프, 센서 데이터 분석, 언어모델 프롬프트 처리 등에서 AI 기반으로 관련 정보를 추출·평가·응답하는 기술을 다룬다.  핵심 기술은 다음과 같다.  - 검색 질의에 대해 질의 매칭 행렬과 객체 매칭 행렬을 생성하고, 이를 3차원 텐서로 구성하여 각 객체의 관련도 점수를 계산한 뒤 검색 결과를 순위화하는 기술 - 감지 장치 내부에서 센서 데이터를 분석하고, 분석 결과에 따라 실행할 동작과 대응 AI 모델을 결정한 후 센서 데이터를 분류하는 기술 - 자연어 입력 텍스

### QA 2 [global] - bm25_without_raptor

Question: 웨이퍼 공정 최적화 기술과 반도체 미세 구조·패키지 방열 기술은 반도체 제조 품질 개선에서 어떻게 상호 보완될 수 있는가?

Best method: dense_bge_m3_with_raptor

Answer: 웨이퍼 공정 최적화 기술과 반도체 미세 구조·패키지 방열 기술은 서로 다른 단계에서 제조 품질을 보완할 수 있다.

웨이퍼 공정 최적화 기술은 공정 수율 관련 데이터와 결함 데이터를 이용해 대상 웨이퍼가 최적 위치에서 벗어난 범위, 척의 유형, 최적 위치를 결정한다. 즉, 제조 공정 중 발생할 수 있는 위치 오차나 결함 요인을 줄여 웨이퍼 단계의 품질과 수율을 개선한다.

반면, 미세 구조·패키지 방열 기술은 3D 적층 칩, 관통 전극, 수평 인접 칩 배치, 큰 로직 칩의 열 특성 최적화, 세라믹 기판과 브릿지 칩 구조체 등을 통해 칩 또는 패키지 단계에서 열적 안정성과 전기적 연결 신뢰성을 높인다.

따라서 전자는 공정 중 결함 발생을 줄이는 역할을 하고, 후자는 제조된 칩이 고성능·고전력 환경에서도 안정적으로 동작하도록 열과 구조 문제를 완화하는 역할을 한다. 두 기술을 함께 적용하면 웨이퍼 제조 단계의 수율 개선과 패키지 단계의 신뢰성 향상이 연결되어, 전체 반도체 제조 품질을 높이는 데 상호 보완적으로 작용할 수 있다.

Score: 4

Context preview: 본 발명의 기술적 사상은, 큰 사이즈를 갖는 고전력, 고성능의 로직 칩의 열적 특성을 최적화할 수 있는 구조의 3D 적층 칩 및 그 3D 적층 칩을 포함한 반도체 패키지를 제공한다. 그 3D 적층 칩은 내부에 제1 관통 전극을 포함한 제1 반도체 칩; 상기 제1 반도체 칩에 수평으로 인접하여 배치된 제2 반도체 칩; 및 상기 제1 반도체 칩과 제2 반도체 칩 상에 배치된 제3 반도체 칩;을 포함하고, 상기 제3 반도체 칩은 상기 제1 반도체 칩보다 큰 사이즈를 갖는다.  본 개시의 기술적 사상은 반도체 공정 변수에 대한 데이터를 수신하는 단계; 컨볼루션(convolution) 알고리즘 및 트랜스포머(transformer) 알고리즘을 통해 이상 감지 모델을 생성하는 단계; 상기 생성된 이상 감지 모델로 상기 데이터를 분류하는 단계;를 포함하는 것을 특징으로 하는 이상 감지 방법을 제공한다.  본 출원은 주 GPU 및 보조 GPU를 포함하는 다중 GPU 시스템을 위한 신경망의 최적화 방법에 관한 것으로, 본 명세서의 일 양상에 따른 최적화 방법은 복수의 레이어를 포함하는 상기 신경망을 획득하는 단계; 상기 신경망의 최적화를 위한 기반 정보를 수집하는 프로파일링 단계 - 상기 기반 정보는 상기 다중 GPU 시스템의 GPU 정보 및 상기 신경망의 구조에 관한 신경망 정보를 포함함 - ; 상기 복수의 레이어 사이의 지점 중 하나인 제1 분기점에서 상기 신경망을 분기하여 상기 신경망을 상기 주 GPU에서 처리되는 제1 주 신경망 및 상기 보조 GPU에서 처리되는 제1 보조 신경망을 포함하는 제1 트리 구조 신경망으로 변환하는 단계; 및 상기 기반 정보에 기초하여 상기 제1 트리 구조 신경망을 최적화하는 단계를 포함한다.  실시예들에 제1 도전형 반도체 물질로 이루어진 바디; 제2 도전형 반도체 물질로 이루어지며, 상기 바디 상에 형성된 소스 및 드레인; 상기 바디 상에 게이트 절연막을 사이에 두고 형성된 제1 게이트; 상기 바디를 사이에 두고 상기 제1 게이트와 대향하도록 형성된 제2 게이트; 및 상기 바디와 제2 게이트 사이에 형성된 전하저장층을 갖는 절연막 스택을 포함하는 반도체 소자 및 이들로 이루어진 뉴럴 네트워크에서 타겟 반도체 소자의 시냅스 가중치를 제어하는 방법에 관련된다.  본 발명의 기술적 사상은 캐비티를 포함하는 세라믹 기판; 상기 세라믹 기판의 하면에 배치되고, 상기 세라믹 기판에 전기적으로 연결되는

### QA 2 [global] - bm25_with_raptor

Question: 웨이퍼 공정 최적화 기술과 반도체 미세 구조·패키지 방열 기술은 반도체 제조 품질 개선에서 어떻게 상호 보완될 수 있는가?

Best method: dense_bge_m3_with_raptor

Answer: 웨이퍼 공정 최적화 기술과 반도체 미세 구조·패키지 방열 기술은 제조 품질 개선에서 서로 다른 단계의 품질 요인을 보완한다.

웨이퍼 공정 최적화 기술은 반도체 공정 변수 데이터를 수집하고, 컨볼루션 알고리즘과 트랜스포머 알고리즘 기반 이상 감지 모델로 데이터를 분류해 공정 이상을 조기에 탐지할 수 있다. 또한 OPC된 레이아웃 데이터의 패턴 꼭지점 좌표를 이용해 MRC 위배 여부를 판단함으로써 미세 패턴 형성 전후의 제조 검증 품질을 높일 수 있다.

반도체 미세 구조 기술은 트렌치, 리세스, 절연막, 소자 분리층, 확산 차단 구조 등을 통해 활성 영역과 핀, 필러, 서브 활성 패턴을 정밀하게 분리하고, 산화막 손실 저감, 동작 전류 개선, 온저항 감소, 고내압 유지, 게이트-드레인 용량 감소 같은 전기적 품질을 확보한다.

패키지 방열 기술은 히트파이프, 고열전도 확산층, 3D 적층 칩 구조 등을 통해 열을 균일하게 방출하고 열 손상 위험을 줄여, 고전력·고성능 반도체의 신뢰성을 높인다.

따라서 공정 최적화 기술은 “불량과 이상을 감지·예방”하는 역할을 하고, 미세 구조·방열 기술은 “소자 성능과 열적 안정성을 구조적으로 확보”하는 역할을 한다. 두 기술을 함께 적용하면 공정 단계의 결함 감소, 미세 패턴 정밀도 향상, 전기적 특성 안정화, 패키지 열 신뢰성 개선이 동시에 가능해져 반도체 제조 품질을 종합적으로 높일 수 있다.

Score: 4

Context preview: 이 특허 묶음은 태양전지용 이온 도핑 장치, 전력 시스템의 시간지연 안정성 판정 방법, 반도체 소자·패키지·메모리 관련 제조 및 구조 기술을 포함한다.  핵심 기술은 진공 분위기에서 기판에 불순물 이온을 조사해 pn 접합을 형성하는 장치, 다중 시간지연 전력 시스템의 모델 차원을 축소해 안정성 여유를 빠르게 판정하는 방법, 그리고 트렌치·리세스·절연막·소자 분리층·확산 차단 구조 등을 이용한 반도체 미세 구조 구현이다.  주요 구성 요소로는 태양전지 제조용 로드락 챔버, 처리 챔버, 이송 챔버, 이송 유닛, 이온 건 및 그리드 플레이트가 있다. 전력 시스템 안정성 판정 기술은 Jordan 표준화, Taylor 전개를 통한 변수 분리, Schur 단순화를 이용한 균형 모델 축소 단계로 구성된다. 반도체 기술은 핀 게이트, LDD·드레인 수직 연결 구조, GaN계 리세스 게이트, 슈퍼정션, 소스·드레인 핑거 및 패드 구조, 도전층·커넥터·유전체 리세스 접속 구조, 히트파이프 포함 패키지, 레이저 박리막, 고열전도 확산층, 더미 퓨즈, 저항 변화 메모리층 등을 포함한다.  목적은 태양전지 기판의 pn 접합 형성, 전력 시스템 안정성 분석의 계산량 감소와 판정 속도 향상, 반도체 소자의 미세화·분리 정밀도·전기적 특성·고내압·방열·메모리 동작 개선에 있다.  효과는 기판 이송과 이온 도핑의 진공 공정 수행, 시간지연 안정성 여유의 신속한 분석, 미세 패턴 형성, 산화막 손실 저감, 동작 전류 개선, 온저항 감소, 고내압 유지, 게이트-드레인 용량 감소, 회로 지연 및 스위칭 불안정 억제, 표면 평탄도 향상, 방열 성능 개선, 퓨즈 선폭 축소, 저항 변화 기반 메모리 비트 저장 구현이다.  제시된 특허들은 반도체 소자, 제조 검증, 패키징, 공정 이상 감지, 적층형 반도체 장치의 데이터 송수신 기술에 관한 것이다.  핵심 내용은 다음과 같다.  - 제1/제2 게이트와 전하저장층을 포함하는 반도체 소자를 이용해 뉴럴 네트워크의 타겟 반도체 소자의 시냅스 가중치를 제어하는 방법에 관한 것이다. 바디, 소스·드레인, 게이트 절연막, 대향 게이트 및 절연막 스택을 주요 구성으로 한다.  - OPC된 반도체 레이아웃 데이터에서 패턴 꼭지점 좌표를 추출하고, 이를 트랜스포머 모델에 입력해 MRC 위배 여부를 출력하는 반도체 장치 제조 방법 및 컴퓨팅 장치이다.  - 큰 사이즈를 갖는 고전력, 고성능 로직 칩의 열적 특성을 최적화할

### QA 2 [global] - dense_bge_m3_without_raptor

Question: 웨이퍼 공정 최적화 기술과 반도체 미세 구조·패키지 방열 기술은 반도체 제조 품질 개선에서 어떻게 상호 보완될 수 있는가?

Best method: dense_bge_m3_with_raptor

Answer: 웨이퍼 공정 최적화 기술은 제조 전·중 단계에서 패턴 품질과 공정 안정성을 높이고, 반도체 미세 구조·패키지 방열 기술은 제조된 구조의 신뢰성과 동작 안정성을 높이는 방식으로 상호 보완될 수 있다.

예를 들어, 트랜스포머 모델을 이용해 OPC된 레이아웃의 꼭지점 좌표를 분석하고 MRC 위배 여부를 출력하면, 실제 웨이퍼 제조 전에 레이아웃 결함 가능성을 줄일 수 있다. 이는 미세 패턴 형성 품질을 개선하는 공정 최적화 역할을 한다.

한편, SDB 영역에서 산화물 손실을 줄이는 트렌치 절연 구조 형성 방법은 미세 구조 수준에서 공정 결함을 줄이고, 3D 적층 칩에서 큰 로직 칩의 열적 특성을 최적화하는 구조나 logic-on-logic 적층에서 한 번에 하나의 칩만 고온이 되도록 하는 패키지 구성은 동작 중 열 문제를 완화한다.

따라서 전자는 제조 패턴과 공정 조건의 오류를 사전에 줄이고, 후자는 소자 구조 및 패키지 단계에서 산화물 손실, 열 집중, 적층 신뢰성 문제를 줄인다. 함께 적용되면 반도체 제조 품질, 수율, 신뢰성 개선에 기여할 수 있다.

Score: 4

Context preview: 트랜스포머 모델을 이용한 반도체 장치의 제조를 위한 방법 및 컴퓨팅 장치가 제공된다. 반도체 장치의 제조를 위한 방법은, 패턴들을 포함하는 OPC된 레이아웃에 대한 OPC된 레이아웃 데이터로부터, 패턴들의 꼭지점들의 좌표들을 추출하고, 꼭지점들의 좌표들을 트랜스포머 모델에 입력하여, OPC된 레이아웃 데이터에 대해 MRC 위배 여부를 출력하는 것을 포함한다.  A semiconductor device manufacturing method is presented. The method entails providing a semiconductor structure comprising a substrate, one or more semiconductor fins on the substrate, and a trench isolation structure around each semiconductor fin, wherein the trench isolation structure comprises a first component intersecting an extension direction of the semiconductor fin and a second component parallel with the extension direction; etching the trench isolation structure to expose a portion of the semiconductor fin; forming a patterned buffer layer on the semiconductor structure covering the second component and having an opening exposing the first component; forming an insulation layer in the opening, with upper surfaces of the insulation layer and the semiconductor fin substantially on the same horizontal level; and removing the buffer layer. This inventive concept reduces, if not eliminates, oxide loss in Single Diffusion Break (SDB) region.  본 발명의 기술적 사상은, 큰 사이즈를 갖는 고전력, 고성능의

### QA 2 [global] - dense_bge_m3_with_raptor

Question: 웨이퍼 공정 최적화 기술과 반도체 미세 구조·패키지 방열 기술은 반도체 제조 품질 개선에서 어떻게 상호 보완될 수 있는가?

Best method: dense_bge_m3_with_raptor

Answer: 웨이퍼 공정 최적화 기술과 반도체 미세 구조·패키지 방열 기술은 제조 품질 개선의 서로 다른 단계에서 상호 보완될 수 있다.

웨이퍼 공정 최적화 기술은 웨이퍼 공정 데이터와 결함 데이터를 이용해 최적 위치나 척 유형을 결정함으로써 공정 조건을 더 안정적으로 맞추는 역할을 한다. 이를 통해 결함 발생 가능성을 줄이고, 미세 패턴이나 소자 구조를 형성하기에 적합한 공정 환경을 제공할 수 있다.

반도체 미세 구조 기술은 트렌치, 리세스, 절연막, 소자 분리층, 확산 차단 구조 등을 이용해 활성 영역, 핀, 필러 등을 정밀하게 분리하고, 산화막 손실 저감, 동작 전류 개선, 온저항 감소, 고내압 유지 같은 전기적 품질을 높인다.

패키지 방열 기술은 히트파이프, 열전도층, 열절연 인터포저, 열 비아, 히트싱크 등을 통해 열을 균일하게 방출하거나 장치 간 열 전달을 제어하여 열 손상 위험을 줄이고 패키지 신뢰성을 높인다.

따라서 웨이퍼 단계에서는 결함·공정 데이터를 기반으로 최적 조건을 정하고, 소자 단계에서는 미세 분리 구조와 전기적 특성 개선 구조로 성능과 수율을 높이며, 패키지 단계에서는 방열 구조로 열적 신뢰성을 확보하는 방식으로 서로 보완될 수 있다.

Score: 5

Context preview: 이 특허 묶음은 AI·신경망 처리, 메모리 중심 연산, 반도체 패키징, 검색·질의응답, 영상·이미지 처리, SoC/NoC 제어 기술을 포괄한다.  **핵심 기술**  - 신경망 실행 결과의 오류율을 비교해 전압·클록 등 전력 설정을 조정하는 전력 관리 기술 - 신경망 파라미터 양자화, 바이너리 뉴럴넷 학습, 모델 압축, LSTM·AI 프로세서 데이터 경로 양자화 기술 - VPU, SIMD, DMA 시퀀서, GEMM·컨볼루션 버퍼링, 시스톨릭 어레이, PE 배열 등 신경망 가속기 구조 - PIM/CIM 기반 메모리 내부 또는 인접 연산, 메모리 요청 스케줄링, 온칩 데이터 이동 제어 기술 - 3D/2.5D 패키징, 칩렛, 메모리 다이·로직 다이 결합, 인터포저 및 열 관리 구조 - 검색 질의 관련도 산정, 센서 데이터 분류, 지식 그래프 생성, 웹 콘텐츠 기반 답변 생성, 언어모델 문맥 압축 기술 - 웨이퍼 공정 수율·결함 데이터를 이용한 최적 위치 결정 및 척 유형 결정 기술 - 포인트 클라우드 기반 3차원 객체 인지 모델을 영상 컨텍스트와 객체 클래스별 앵커 박스에 맞게 학습하는 기술 - 이미지 분류용 프록시 모델 학습, 동일 인물 이미지 검색, 이미지 코드의 해밍 비교 처리 기술 - ASIC/SoC/NoC에서 암호화폐 채굴, 외부 트래픽 제어, ECC 처리, NoC 라우팅, 자율주행차용 칩렛 워크로드 스케줄링, ML 가속기 구성을 수행하는 기술  **목적**  - 허용 가능한 오류 범위 내에서 신경망 전력 효율을 높이는 것 - 모델 크기, 메모리 사용량, 데이터 이동량, 연산량을 줄이는 것 - 메모리 내부 연산과 병렬 처리를 통해 AI·그래픽·데이터베이스·머신러닝 작업을 가속하는 것 - 멀티레인 AI 시스템, DMA, 메모리 접근, 칩렛 간 작업 분산을 효율적으로 제어하는 것 - 영상 생성·복원, 객체 인지, 이미지 검색 및 이미지 코드 비교 성능을 높이는 것 - 검색·질의응답·지식 그래프·언어모델 입력 처리에서 관련 정보 추출과 응답 생성을 효율화하는 것 - 반도체 공정, 웨이퍼 위치, 패키지 구조, 메모리 신뢰성 및 열 특성을 개선하는 것  **주요 구성 요소**  - 오류율 산정 절차, 애플리케이션 오류 허용치, 전압·클록 제어부 - 레인별 오케스트레이터, 상위 오케스트레이터, 활성 컴포넌트 제어 구조 - VPU 데이터 경로, SIMD 레인, min/max 수집기, DMA 시퀀서, 로드·스토어·퍼뮤트

### QA 3 [global] - bm25_without_raptor

Question: 3차원 객체 인지, 이미지 분류, 동일 인물 이미지 검색 기술을 함께 고려할 때 비전 AI 시스템의 정확도와 처리 속도를 높이는 공통 전략은 무엇인가?

Best method: bm25_with_raptor

Answer: 공통 전략은 **입력 영상/이미지의 특성에 맞게 처리 대상을 먼저 좁히고, 그에 맞는 모델·데이터·비교 기준을 선택적으로 적용하는 것**이다.

구체적으로는 3차원 객체 인지에서는 영상 컨텍스트에 따라 관심 객체 그룹과 앵커 박스를 제한하고, 이미지 분류에서는 라벨링 데이터와 비라벨링 데이터를 구분한 뒤 프록시 모델과 샘플링을 활용하며, 동일 인물 이미지 검색에서는 얼굴 영역을 추출해 파레트 데이터로 비교 대상을 구성한다.

즉, 전체 데이터를 무차별적으로 처리하는 대신 **컨텍스트 추정, 후보군 제한, 특징 추출, 적응적 모델 설정 또는 프록시 학습**을 통해 불필요한 연산을 줄이고, 관심 대상에 집중함으로써 정확도와 처리 속도를 함께 높이는 전략이다.

Score: 4

Context preview: 포인트 클라우드 기반 3차원 객체 인지 모델의 컨텍스트 별 학습 방법이 제공된다. 본 발명의 실시예에 따른 객체 인지 모델 학습 방법은, 3차원 영상 데이터를 입력받고, 입력된 3차원 영상의 컨텍스트를 추정하며, 추정된 컨텍스트에 매칭되는 객체 그룹을 선택하고, 선택된 객체 그룹에 포함된 각 객체들에 대한 앵커 박스들을 결정하며, 객체들을 인지하기 위한 인공지능 모델인 객체 인지 모델을 결정 결과에 따라 설정하고, 입력된 3차원 영상 데이터를 이용하여 설정된 객체 인지 모델을 학습시킨다. 이에 의해, 영상 컨텍스트에 따라 인식할 관심 객체들을 제한하고, 관심 객체의 클래스에 따라 적용할 앵커 박스를 적응적으로 결정하여, 객체 인지 모델을 생성하고 설정하여 학습시킴으로써, 트레이드 오프 관계에 있는 객체 인지 모델의 정확도와 속도 모두를 향상시킬 수 있게 된다.  일 실시예에 따른 동일한 인물이 포함된 이미지를 검색하기 위한 이미지 처리 시스템은, 이미지 데이터가 저장되는 제1 저장 모듈, 검색 대상이 되는 인물이 포함된 입력 데이터를 입력 받는 입력 모듈, 상기 이미지 데이터에 포함된 얼굴 영역을 추출하여 얼굴 데이터를 생성하는 얼굴 검출 모듈, 적어도 하나의 상기 얼굴 데이터를 포함하는 파레트 데이터를 생성하는 파레트 데이터 생성 모듈, 및 상기 입력 데이터 및 상기 파레트 데이터를 비교하여 생성된 결과 정보를 기반으로 상기 입력 데이터와 동일한 인물이 포함된 상기 이미지 데이터를 출력하는 이미지 출력 모듈을 포함하는 이미지 처리 장치;를 포함할 수 있다.  본 발명은 이미지 분류 장치에 의해 수행되는 방법에 있어서, 이미지 분류가 필요한 이미지 데이터를 획득하는 단계, 이미지 데이터에서 라벨링 데이터 및 비 라벨링 데이터로 분류하는 단계, 라벨링 데이터 중 일부를 활용하여 프록시 모델을 학습하는 단계, 비 라벨링 데이터 중 샘플링 처리를 통해 비 라벨링 데이터를 분류하는 단계, 및 분류된 비 라벨링 데이터 중 일부 데이터를 프록시 모델에 입력하여 학습하는 단계를 포함하는 비전 기반 산업 응용 프로그램에서 프록시 모델을 활용한 라벨링 데이터를 획득하는 방법 및 그 장치에 관한 것이다.  프로세싱부를 포함하는 이종 메모리 시스템을 억세스하는 데이터 처리 시스템 및 방법이 기술된다. 이종 메모리 시스템은 ,메모리 모듈 및 메모리-내-처리(Processing-In-Memory: PIM) 회로를 포함하는 고대역 메모

### QA 3 [global] - bm25_with_raptor

Question: 3차원 객체 인지, 이미지 분류, 동일 인물 이미지 검색 기술을 함께 고려할 때 비전 AI 시스템의 정확도와 처리 속도를 높이는 공통 전략은 무엇인가?

Best method: bm25_with_raptor

Answer: 공통 전략은 **입력 영상·이미지의 특성과 목적에 맞게 처리 대상을 선별하고, 적응형 모델 또는 비교 구조를 적용해 불필요한 연산과 데이터 처리를 줄이는 것**이다.

구체적으로는 다음과 같다.

- 3차원 객체 인지에서는 영상 컨텍스트를 추정해 관심 객체 그룹만 선택하고, 객체 클래스별 앵커 박스를 적응적으로 적용한다.
- 이미지 분류에서는 라벨링 데이터 일부로 프록시 모델을 학습하고, 샘플링된 비라벨링 데이터를 활용해 학습 효율을 높인다.
- 동일 인물 이미지 검색에서는 얼굴 검출과 파레트 데이터를 이용해 입력 데이터와 동일 인물이 포함된 이미지를 찾는다.
- 이미지 코드 비교에서는 이진 임베딩 등 이미지 코드를 메모리 근접 처리 유닛이나 메모리 컨트롤러에서 해밍 비교해 처리량을 높인다.

따라서 공통적으로 **컨텍스트·클래스·라벨·얼굴 특징·이미지 코드 등 핵심 특징을 이용해 처리 범위를 줄이고, 적응형 학습·검색·비교 방식을 적용함으로써 정확도와 처리 속도를 함께 향상시키는 전략**이라고 볼 수 있다.

Score: 5

Context preview: 이 특허 묶음은 AI·신경망 처리, 메모리 중심 연산, 반도체 패키징, 검색·질의응답, 영상·이미지 처리, SoC/NoC 제어 기술을 포괄한다.  **핵심 기술**  - 신경망 실행 결과의 오류율을 비교해 전압·클록 등 전력 설정을 조정하는 전력 관리 기술 - 신경망 파라미터 양자화, 바이너리 뉴럴넷 학습, 모델 압축, LSTM·AI 프로세서 데이터 경로 양자화 기술 - VPU, SIMD, DMA 시퀀서, GEMM·컨볼루션 버퍼링, 시스톨릭 어레이, PE 배열 등 신경망 가속기 구조 - PIM/CIM 기반 메모리 내부 또는 인접 연산, 메모리 요청 스케줄링, 온칩 데이터 이동 제어 기술 - 3D/2.5D 패키징, 칩렛, 메모리 다이·로직 다이 결합, 인터포저 및 열 관리 구조 - 검색 질의 관련도 산정, 센서 데이터 분류, 지식 그래프 생성, 웹 콘텐츠 기반 답변 생성, 언어모델 문맥 압축 기술 - 웨이퍼 공정 수율·결함 데이터를 이용한 최적 위치 결정 및 척 유형 결정 기술 - 포인트 클라우드 기반 3차원 객체 인지 모델을 영상 컨텍스트와 객체 클래스별 앵커 박스에 맞게 학습하는 기술 - 이미지 분류용 프록시 모델 학습, 동일 인물 이미지 검색, 이미지 코드의 해밍 비교 처리 기술 - ASIC/SoC/NoC에서 암호화폐 채굴, 외부 트래픽 제어, ECC 처리, NoC 라우팅, 자율주행차용 칩렛 워크로드 스케줄링, ML 가속기 구성을 수행하는 기술  **목적**  - 허용 가능한 오류 범위 내에서 신경망 전력 효율을 높이는 것 - 모델 크기, 메모리 사용량, 데이터 이동량, 연산량을 줄이는 것 - 메모리 내부 연산과 병렬 처리를 통해 AI·그래픽·데이터베이스·머신러닝 작업을 가속하는 것 - 멀티레인 AI 시스템, DMA, 메모리 접근, 칩렛 간 작업 분산을 효율적으로 제어하는 것 - 영상 생성·복원, 객체 인지, 이미지 검색 및 이미지 코드 비교 성능을 높이는 것 - 검색·질의응답·지식 그래프·언어모델 입력 처리에서 관련 정보 추출과 응답 생성을 효율화하는 것 - 반도체 공정, 웨이퍼 위치, 패키지 구조, 메모리 신뢰성 및 열 특성을 개선하는 것  **주요 구성 요소**  - 오류율 산정 절차, 애플리케이션 오류 허용치, 전압·클록 제어부 - 레인별 오케스트레이터, 상위 오케스트레이터, 활성 컴포넌트 제어 구조 - VPU 데이터 경로, SIMD 레인, min/max 수집기, DMA 시퀀서, 로드·스토어·퍼뮤트

### QA 3 [global] - dense_bge_m3_without_raptor

Question: 3차원 객체 인지, 이미지 분류, 동일 인물 이미지 검색 기술을 함께 고려할 때 비전 AI 시스템의 정확도와 처리 속도를 높이는 공통 전략은 무엇인가?

Best method: bm25_with_raptor

Answer: 공통 전략은 **처리 대상을 먼저 선별·구조화한 뒤, 목적에 맞는 경량화된 비교/학습 단위를 사용하여 모델이 집중하도록 하는 것**입니다.

구체적으로는 다음과 같습니다.

- 3차원 객체 인지에서는 영상 컨텍스트에 따라 관심 객체 그룹을 제한하고, 객체 클래스에 맞는 앵커 박스를 적응적으로 결정한다.
- 이미지 분류에서는 라벨링 데이터와 비라벨링 데이터를 구분하고, 샘플링 및 프록시 모델을 활용해 학습 대상을 효율적으로 확장한다.
- 동일 인물 이미지 검색에서는 전체 이미지가 아니라 얼굴 영역을 추출하고, 파레트 데이터와 입력 데이터를 비교한다.

따라서 공통적으로는 **불필요한 데이터나 객체 후보를 줄이고, 컨텍스트·라벨·얼굴 특징 등 핵심 정보 중심으로 학습 또는 비교를 수행하는 전략**이 정확도와 처리 속도를 함께 높이는 방법이다.

Score: 3

Context preview: 포인트 클라우드 기반 3차원 객체 인지 모델의 컨텍스트 별 학습 방법이 제공된다. 본 발명의 실시예에 따른 객체 인지 모델 학습 방법은, 3차원 영상 데이터를 입력받고, 입력된 3차원 영상의 컨텍스트를 추정하며, 추정된 컨텍스트에 매칭되는 객체 그룹을 선택하고, 선택된 객체 그룹에 포함된 각 객체들에 대한 앵커 박스들을 결정하며, 객체들을 인지하기 위한 인공지능 모델인 객체 인지 모델을 결정 결과에 따라 설정하고, 입력된 3차원 영상 데이터를 이용하여 설정된 객체 인지 모델을 학습시킨다. 이에 의해, 영상 컨텍스트에 따라 인식할 관심 객체들을 제한하고, 관심 객체의 클래스에 따라 적용할 앵커 박스를 적응적으로 결정하여, 객체 인지 모델을 생성하고 설정하여 학습시킴으로써, 트레이드 오프 관계에 있는 객체 인지 모델의 정확도와 속도 모두를 향상시킬 수 있게 된다.  일 실시예에 따른 동일한 인물이 포함된 이미지를 검색하기 위한 이미지 처리 시스템은, 이미지 데이터가 저장되는 제1 저장 모듈, 검색 대상이 되는 인물이 포함된 입력 데이터를 입력 받는 입력 모듈, 상기 이미지 데이터에 포함된 얼굴 영역을 추출하여 얼굴 데이터를 생성하는 얼굴 검출 모듈, 적어도 하나의 상기 얼굴 데이터를 포함하는 파레트 데이터를 생성하는 파레트 데이터 생성 모듈, 및 상기 입력 데이터 및 상기 파레트 데이터를 비교하여 생성된 결과 정보를 기반으로 상기 입력 데이터와 동일한 인물이 포함된 상기 이미지 데이터를 출력하는 이미지 출력 모듈을 포함하는 이미지 처리 장치;를 포함할 수 있다.  In one embodiment, a method includes receiving, from a client system associated with a user, a search query comprising a number of query terms, generating a query match-matrix for the search query, identifying a number of objects matching the search query, retrieving, for each identified object, an object match-matrix for the identified object, constructing, for each identified object, a three-dimensional tensor for the ide

### QA 3 [global] - dense_bge_m3_with_raptor

Question: 3차원 객체 인지, 이미지 분류, 동일 인물 이미지 검색 기술을 함께 고려할 때 비전 AI 시스템의 정확도와 처리 속도를 높이는 공통 전략은 무엇인가?

Best method: bm25_with_raptor

Answer: 공통 전략은 **처리 대상과 연산 범위를 줄이고, 데이터 특성에 맞게 모델·특징·비교 방식을 적응적으로 선택하는 것**이다.

구체적으로는 3차원 객체 인지에서는 영상 컨텍스트에 맞는 객체 그룹만 선택하고 객체 클래스별 앵커 박스를 적용한다. 이미지 분류에서는 라벨링 데이터와 비라벨링 데이터를 구분한 뒤 프록시 모델과 샘플링을 활용해 학습 효율을 높인다. 동일 인물 이미지 검색에서는 얼굴 검출 및 파레트 데이터 등을 이용해 동일 인물 후보 이미지를 효과적으로 찾는다.

따라서 공통적으로 **관심 대상만 선별하고, 상황·클래스·데이터 유형에 맞는 모델 또는 특징 표현을 적용해 불필요한 연산을 줄임으로써 정확도와 처리 속도를 함께 향상시키는 전략**이라고 볼 수 있다.

Score: 4

Context preview: 첫 번째는 웨이퍼의 최적 위치를 결정하는 방법에 관한 것이다. 대상 웨이퍼의 공정 수율과 관련된 공정 데이터를 획득하고, 이를 기반으로 대상 웨이퍼가 기저장된 최적 위치로부터 벗어난 이탈 범위를 판단한다. 또한 학습된 인공지능 모델을 이용해 대상 웨이퍼의 결함 데이터에 대응되는 척의 유형을 결정하고, 결정된 척의 유형 및 이탈 범위에 기반하여 대상 웨이퍼의 최적 위치를 결정한다.  두 번째는 포인트 클라우드 기반 3차원 객체 인지 모델을 영상 컨텍스트별로 학습하는 방법에 관한 것이다. 3차원 영상 데이터를 입력받아 해당 영상의 컨텍스트를 추정하고, 그 컨텍스트에 맞는 객체 그룹을 선택한다. 이후 선택된 객체 그룹에 포함된 각 객체 클래스에 대해 적합한 앵커 박스를 결정하고, 그 결과에 따라 객체 인지 인공지능 모델을 설정한 뒤 입력된 3차원 영상 데이터로 학습시킨다. 이를 통해 영상 상황에 따라 인식 대상 객체를 관심 객체로 제한하고, 객체 클래스별 앵커 박스를 적응적으로 적용함으로써 객체 인지 모델의 정확도와 처리 속도를 함께 향상시키는 것을 목적으로 한다.  본 발명은 포인트 클라우드 기반 3차원 객체 인지 모델을 영상 컨텍스트별로 학습하는 방법에 관한 것이다.  3차원 영상 데이터를 입력받아 해당 영상의 컨텍스트를 추정하고, 그 컨텍스트에 맞는 객체 그룹을 선택한다. 이후 선택된 객체 그룹에 포함된 각 객체 클래스에 대해 적합한 앵커 박스를 결정하고, 그 결과에 따라 객체 인지 인공지능 모델을 설정한 뒤 입력된 3차원 영상 데이터로 학습시킨다.  이를 통해 영상 상황에 따라 인식 대상 객체를 관심 객체로 제한하고, 객체 클래스별 앵커 박스를 적응적으로 적용함으로써 객체 인지 모델의 정확도와 처리 속도를 함께 향상시키는 것을 목적으로 한다.  포인트 클라우드 기반 3차원 객체 인지 모델의 컨텍스트 별 학습 방법이 제공된다. 본 발명의 실시예에 따른 객체 인지 모델 학습 방법은, 3차원 영상 데이터를 입력받고, 입력된 3차원 영상의 컨텍스트를 추정하며, 추정된 컨텍스트에 매칭되는 객체 그룹을 선택하고, 선택된 객체 그룹에 포함된 각 객체들에 대한 앵커 박스들을 결정하며, 객체들을 인지하기 위한 인공지능 모델인 객체 인지 모델을 결정 결과에 따라 설정하고, 입력된 3차원 영상 데이터를 이용하여 설정된 객체 인지 모델을 학습시킨다. 이에 의해, 영상 컨텍스트에 따라 인식할 관심 객체들을 제한하고, 관심 객체의 클

### QA 4 [global] - bm25_without_raptor

Question: AI 가속기와 SoC/NoC 기반 집적회로에서 메모리 접근 제어, ECC 처리, 외부 트래픽 제어, DMA 및 PE 배열 기술을 함께 적용하는 목적은 무엇인가?

Best method: bm25_with_raptor

Answer: 목적은 AI/신경망 연산과 메모리 연산을 더 효율적이고 안정적으로 수행하기 위한 것이다.

제공된 문맥에 따르면, 이러한 기술들은 다음을 위해 함께 적용된다.

- 메모리 내부 또는 근처에서 연산을 수행하여 CPU와 메모리 사이의 불필요한 데이터 전송을 줄임
- PIM 연산, DMA 전송, PE 배열 기반 병렬 연산을 통해 처리량과 성능을 높임
- 메모리 트래픽을 개선하고 외부 인터페이스의 부담을 줄임
- NoC 기반 집적회로에서 메모리 접근 시 ECC 데이터를 계산하여 읽기/쓰기 트랜잭션의 신뢰성을 높임
- 신경망 구조나 데이터 지역성에 따라 메모리 시스템과 프로세싱 엘리먼트 어레이를 제어하여 연산 효율을 높임

따라서 종합하면, 목적은 **AI 가속기 및 SoC/NoC 기반 시스템에서 메모리 접근과 데이터 이동을 최적화하고, 오류 정정 신뢰성을 확보하며, 외부 트래픽과 CPU 부담을 줄여 전체 연산 성능과 에너지 효율을 향상시키는 것**이다.

Score: 4

Context preview: 본 발명에 따른 메모리 장치는, 외부 장치로부터 제어 신호들을 수신하는 복수의 핀들, 제 1 동작 모드 및 제 2 동작 모드에서 활성화되고 제 1 메모리 셀들을 갖는 제 1 뱅크, 상기 제 1 동작 모드에서 비활성화 되고, 상기 제 2 동작 모드에서 활성화되고, 제 2 메모리 셀들을 갖는 제 2 뱅크, 상기 제 2 동작 모드에서 상기 제 1 뱅크의 상기 제 1 메모리 셀들로부터 출력된 제 1 데이터와 상기 제 2 뱅크의 상기 제 2 메모리 셀들로부터 출력된 제 2 데이터를 연산하는 프로세싱 유닛, 및 상기 복수의 핀들을 통하여 수신된 제어 신호들에 응답하여 상기 제 1 동작 모드 및 상기 제 2 동작 모드를 지시하는 모드 정보를 선택하고, 상기 선택된 모드 정보에 응답하여 적어도 하나의 메모리 파라미터, 적어도 하나의 모드 레지스터 셋 설정값, 혹은 리프레쉬 모드를 제어하는 PIM(Processing-In-Memory) 모드 제어기를 포함할 수 있다.  적층형 반도체 장치는, 제 1 의사 채널 및 제 2 의사 채널을 각각 포함하는 다수의 채널들; 및 상기 제 1 의사 채널 또는 상기 제 2 의사 채널을 지정하는 채널 지정 신호(PC_ASS) 및 대응하는 채널의 위치 정보 신호(LOCATE_F)에 따라 채널 커맨드를 출력하고, 상기 채널 커맨드에 따라 상기 대응하는 채널과 하부 칩 사이에서 제 1 및 제 2 데이터 워드를 송수신하는 각 전달 제어 회로를 포함하는 다수의 전달 제어 회로들을 포함하는 상부 칩을 포함할 수 있다.  프로세싱부를 포함하는 이종 메모리 시스템을 억세스하는 데이터 처리 시스템 및 방법이 기술된다. 이종 메모리 시스템은 ,메모리 모듈 및 메모리-내-처리(Processing-In-Memory: PIM) 회로를 포함하는 고대역 메모리(HBM)으로 구성되고, 메모리 콘트롤러와 결합된다. 메모리 콘트롤러는 HBM의 PIM 회로에서 연산 작업이 실행될 때, 보더 인덱스 값을 이용하여 연산 작업에 요구되는 데이터 어레이를 메모리 모듈 또는 HBM으로부터 검색하고, 메모리 모듈 및 HBM 각각에 지정된 물리 주소 공간을 사용하는 메모리 모듈 명령어 세트 및 HBM 명령어 세트를 생성한다.  기판; 및 상기 기판 상의 반도체 칩; 을 포함하되, 상기 기판은: 내부 절연층; 상기 내부 절연층 내의 재배선층; 상기 내부 절연층 상의 외부 절연층; 상기 재배선층과 전기적으로 연결되는 상기 외부 절연층 내의 연결

### QA 4 [global] - bm25_with_raptor

Question: AI 가속기와 SoC/NoC 기반 집적회로에서 메모리 접근 제어, ECC 처리, 외부 트래픽 제어, DMA 및 PE 배열 기술을 함께 적용하는 목적은 무엇인가?

Best method: bm25_with_raptor

Answer: 목적은 AI 가속기와 SoC/NoC 기반 집적회로에서 데이터 이동, 메모리 접근, 트래픽, 오류 정정, 병렬 연산을 효율적으로 제어하여 전체 처리 성능과 신뢰성을 높이는 것이다.

구체적으로는 메모리 접근과 DMA 전송을 효율화해 데이터 이동 지연과 외부 메모리 접근을 줄이고, PE 배열·시스톨릭 어레이 등을 통해 신경망 연산을 병렬 가속하며, ECC 처리로 메모리 대상 읽기·쓰기 트랜잭션의 신뢰성을 높이는 데 있다. 또한 외부 트래픽 제어를 통해 신뢰되지 않은 외부 장치로 인한 NoC 부하를 줄이고, NoC 라우팅과 워크로드 스케줄링을 효율화해 전력 효율, 대역폭 활용, 처리량, 시스템 안정성을 개선하려는 목적이다.

Score: 5

Context preview: 이 특허 묶음은 AI·신경망 처리, 메모리 중심 연산, 반도체 패키징, 검색·질의응답, 영상·이미지 처리, SoC/NoC 제어 기술을 포괄한다.  **핵심 기술**  - 신경망 실행 결과의 오류율을 비교해 전압·클록 등 전력 설정을 조정하는 전력 관리 기술 - 신경망 파라미터 양자화, 바이너리 뉴럴넷 학습, 모델 압축, LSTM·AI 프로세서 데이터 경로 양자화 기술 - VPU, SIMD, DMA 시퀀서, GEMM·컨볼루션 버퍼링, 시스톨릭 어레이, PE 배열 등 신경망 가속기 구조 - PIM/CIM 기반 메모리 내부 또는 인접 연산, 메모리 요청 스케줄링, 온칩 데이터 이동 제어 기술 - 3D/2.5D 패키징, 칩렛, 메모리 다이·로직 다이 결합, 인터포저 및 열 관리 구조 - 검색 질의 관련도 산정, 센서 데이터 분류, 지식 그래프 생성, 웹 콘텐츠 기반 답변 생성, 언어모델 문맥 압축 기술 - 웨이퍼 공정 수율·결함 데이터를 이용한 최적 위치 결정 및 척 유형 결정 기술 - 포인트 클라우드 기반 3차원 객체 인지 모델을 영상 컨텍스트와 객체 클래스별 앵커 박스에 맞게 학습하는 기술 - 이미지 분류용 프록시 모델 학습, 동일 인물 이미지 검색, 이미지 코드의 해밍 비교 처리 기술 - ASIC/SoC/NoC에서 암호화폐 채굴, 외부 트래픽 제어, ECC 처리, NoC 라우팅, 자율주행차용 칩렛 워크로드 스케줄링, ML 가속기 구성을 수행하는 기술  **목적**  - 허용 가능한 오류 범위 내에서 신경망 전력 효율을 높이는 것 - 모델 크기, 메모리 사용량, 데이터 이동량, 연산량을 줄이는 것 - 메모리 내부 연산과 병렬 처리를 통해 AI·그래픽·데이터베이스·머신러닝 작업을 가속하는 것 - 멀티레인 AI 시스템, DMA, 메모리 접근, 칩렛 간 작업 분산을 효율적으로 제어하는 것 - 영상 생성·복원, 객체 인지, 이미지 검색 및 이미지 코드 비교 성능을 높이는 것 - 검색·질의응답·지식 그래프·언어모델 입력 처리에서 관련 정보 추출과 응답 생성을 효율화하는 것 - 반도체 공정, 웨이퍼 위치, 패키지 구조, 메모리 신뢰성 및 열 특성을 개선하는 것  **주요 구성 요소**  - 오류율 산정 절차, 애플리케이션 오류 허용치, 전압·클록 제어부 - 레인별 오케스트레이터, 상위 오케스트레이터, 활성 컴포넌트 제어 구조 - VPU 데이터 경로, SIMD 레인, min/max 수집기, DMA 시퀀서, 로드·스토어·퍼뮤트

### QA 4 [global] - dense_bge_m3_without_raptor

Question: AI 가속기와 SoC/NoC 기반 집적회로에서 메모리 접근 제어, ECC 처리, 외부 트래픽 제어, DMA 및 PE 배열 기술을 함께 적용하는 목적은 무엇인가?

Best method: bm25_with_raptor

Answer: 목적은 AI/ML 연산의 처리량과 효율을 높이면서, SoC/NoC 환경에서 데이터 이동과 메모리 접근을 안정적으로 제어하기 위한 것이다.

구체적으로는 PE 배열, 캐시, DMA, 로드/스토어 및 메모리 접근 제어를 통해 연산 데이터를 빠르게 공급하고 재구성하여 VPU나 AI 가속기의 성능을 높인다. ECC 처리는 메모리 read/write 또는 내부 처리 결과의 오류 정정과 데이터 무결성을 보장한다. 외부 트래픽 제어는 untrusted device로부터 들어오는 과도한 트래픽이 NoC 내부 트래픽에 악영향을 주지 않도록 제한한다.

따라서 이들 기술을 함께 적용하는 목적은 고속 AI 연산, 효율적인 데이터 이동, 저장 및 통신 자원 절감, 프로그래밍 복잡도 감소, 데이터 신뢰성 확보, 그리고 NoC 기반 SoC의 안정적인 트래픽 관리를 달성하는 것이다.

Score: 5

Context preview: In various examples, a VPU and associated components may be optimized to improve VPU performance and throughput. For example, the VPU may include a min/max collector, automatic store predication functionality, a SIMD data path organization that allows for inter-lane sharing, a transposed load/store with stride parameter functionality, a load with permute and zero insertion functionality, hardware, logic, and memory layout functionality to allow for two point and two by two point lookups, and per memory bank load caching capabilities. In addition, decoupled accelerators may be used to offload VPU processing tasks to increase throughput and performance, and a hardware sequencer may be included in a DMA system to reduce programming complexity of the VPU and the DMA system. The DMA and VPU may execute a VPU configuration mode that allows the VPU and DMA to operate without a processing controller for performing dynamic region based data movement operations.  A deep neural network hardware accelerator comprises: an AXI-4 bus interface, an input cache area, an output cache area, a weighting cache area, a weighting index cache area, an encoding module, a configurable state controller modul

### QA 4 [global] - dense_bge_m3_with_raptor

Question: AI 가속기와 SoC/NoC 기반 집적회로에서 메모리 접근 제어, ECC 처리, 외부 트래픽 제어, DMA 및 PE 배열 기술을 함께 적용하는 목적은 무엇인가?

Best method: bm25_with_raptor

Answer: 목적은 AI·신경망 연산과 SoC/NoC 내부 데이터 처리를 더 효율적이고 안정적으로 수행하는 것이다.

구체적으로는 메모리 접근과 데이터 이동을 줄이고, DMA와 PE 배열을 통해 병렬 연산 처리량을 높이며, ECC 처리로 메모리 대상 트랜잭션의 신뢰성을 확보하고, 외부 트래픽 제어로 신뢰되지 않은 장치가 NoC에 과도한 부하를 유발하는 것을 억제하는 데 있다. 결과적으로 연산 성능, 전력 효율, 메모리 대역폭 효율, 통신 안정성 및 시스템 신뢰성을 개선하려는 것이다.

Score: 5

Context preview: 이 특허 묶음은 ASIC, SoC, NoC 기반 집적회로에서 분산원장 상호작용, 외부 트래픽 제어, 메모리 대상 트랜잭션의 ECC 처리, NoC 라우팅, 자율주행차용 칩렛 SoC의 워크로드 스케줄링, ML 가속기 SoC 구성을 다룬다.  핵심 기술은 다수의 해시 다이와 이를 제어하는 컨트롤 다이를 하나의 집적회로 패키지에 통합한 암호화폐 채굴용 ASIC, 신뢰되지 않은 외부 장치로부터 수신되는 외부 트래픽 양을 감시하고 트래픽 정책 위반을 검출하면 해당 외부 장치의 메시지로 인해 NoC에 발생하는 트래픽을 줄이는 호스트 SoC, 메모리 대상 읽기·쓰기 트랜잭션을 수신해 ECC 데이터를 계산하고 메모리 컨트롤러로 나가는 트랜잭션을 제공하는 NoC 기반 IC이다.  또한 SoC의 NoC 라우팅에서는 매퍼가 트랜잭션의 목적지 ID를 식별하며, 하드웨어 요소가 목적지 ID를 제공하면 주소 맵을 우회하고, 목적지 ID가 제공되지 않으면 트랜잭션의 주소를 이용해 목적지 ID를 식별한다. 자율주행차용 칩렛 기반 SoC는 중앙 칩렛과 센서 데이터 입력 칩렛을 포함하고, 센서 데이터 입력 칩렛이 차량 센서로부터 수신한 센서 데이터를 캐시 메모리에 저장하면 스케줄링 프로그램이 캐시에 저장된 센서 데이터에 적어도 부분적으로 기초해 병렬 워크로드 파이프라인의 워크로드 실행을 스케줄링한다. ML 가속기 SoC는 ML 가속 코어들의 세트, NoC, 추론용 비디오 후처리 모듈, 비디오 디코더를 포함한다.  이 특허 묶음은 ASIC, SoC, NoC 기반 집적회로에서 분산원장 상호작용, 외부 트래픽 제어, 메모리 대상 트랜잭션의 ECC 처리, NoC 라우팅, 자율주행차용 칩렛 SoC의 워크로드 스케줄링, ML 가속기 SoC 구성을 다룬다.  핵심 기술은 다음과 같다.  - 암호화폐 채굴용 ASIC은 다수의 해시 다이와 이를 제어하는 컨트롤 다이로 구성되며, 컨트롤 다이는 해시 다이보다 큰 공정 노드로 형성된다. 다이들은 인터커넥터로 전기적으로 연결되고 하나의 집적회로 패키지에 봉입된다. - 호스트 SoC는 내부 블록 간 로컬 트래픽을 전송하는 NoC, 신뢰되지 않은 외부 장치로부터 메시지를 수신하는 외부 프로세서 링크, 및 트래픽 컨트롤러를 포함한다. 트래픽 컨트롤러는 외부 트래픽 양을 감시하고, 트래픽 정책 위반을 검출하면 해당 외부 장치의 메시지로 인해 NoC에 발생하는 트래픽을 줄인다. - NoC 기반 IC는 마스터 장치, 메모리 컨

### QA 5 [local] - bm25_without_raptor

Question: 15-615713 특허에서 온라인 소셜 네트워크 검색 결과의 순위는 어떤 기준으로 결정되나요?

Best method: dense_bge_m3_without_raptor

Answer: 제공된 문맥에는 15-615713 특허나 온라인 소셜 네트워크 검색 결과의 순위 결정 기준에 대한 내용이 없습니다. 따라서 답변하기에 문맥이 충분하지 않습니다.

Score: 1

Context preview: 본 명세서는 뉴럴 네트워크 프로세서를 개시하고 있다. 본 발명의 일 실시예는, 뉴럴 네트워크의 프로세싱을 수행하도록 구성되는 프로세싱 유닛에 있어서, 하나 이상의 인스트럭션을 구비하는 태스크들을 저장하도록 구성되는 인스트럭션 메모리와, 상기 태스크들과 연관된 데이터를 저장하도록 구성되는 데이터 메모리와, 상기 태스크들을 대상으로 데이터 준비 여부를 체크하고, 데이터 준비가 완료된 태스크의 순서대로 상기 태스크들의 준비 완료 여부를 컨트롤 플로우 엔진에 통지하도록 구성되는 데이터 플로우 엔진과, 상기 데이터 플로우 엔진으로부터 통지 받은 순서대로 태스크를 실행하도록 구성되는 컨트롤 플로우 엔진, 그리고, 상기 컨트롤 플로우 엔진이 실행하도록 제어하는 태스크의 하나 이상의 인스트럭션에 따른 연산을 수행하도록 구성되는 수행 유닛을 포함하는 뉴럴 네트워크 프로세싱 유닛을 제공한다.  프로세싱 유닛들이 공통적으로 공유할 공유 오퍼랜드를 입력 피처맵의 픽셀값 또는 커널의 웨이트값 중 어느 하나로 결정하고, 결정된 공유 오퍼랜드를 기초로 병렬화된 연산들을 수행하는 방법 및 이를 위한 뉴럴 네트워크 장치를 제공한다.  일 실시예에 따른 동일한 인물이 포함된 이미지를 검색하기 위한 이미지 처리 시스템은, 이미지 데이터가 저장되는 제1 저장 모듈, 검색 대상이 되는 인물이 포함된 입력 데이터를 입력 받는 입력 모듈, 상기 이미지 데이터에 포함된 얼굴 영역을 추출하여 얼굴 데이터를 생성하는 얼굴 검출 모듈, 적어도 하나의 상기 얼굴 데이터를 포함하는 파레트 데이터를 생성하는 파레트 데이터 생성 모듈, 및 상기 입력 데이터 및 상기 파레트 데이터를 비교하여 생성된 결과 정보를 기반으로 상기 입력 데이터와 동일한 인물이 포함된 상기 이미지 데이터를 출력하는 이미지 출력 모듈을 포함하는 이미지 처리 장치;를 포함할 수 있다.  일 측면에 따른 뉴럴 네트워크 장치에서 연산을 수행하는 방법은, 적어도 하나의 입력 피처맵 및 적어도 하나의 커널을 포함하는 복수의 연산 그룹들과, 복수의 연산 그룹들 각각에 대응하는 태그(tag) 정보를 획득하고, 복수의 연산 유닛들 중 유휴 상태인 연산 유닛을 결정할 수 있다.  유휴 상태인 연산 유닛에서, 복수의 연산 그룹들 중 소정의 연산 그룹에 포함된 입력 피처맵 및 커널 간의 컨벌루션 연산을 수행함으로써 중간 피처맵을 생성하고, 소정의 연산 그룹에 대응하는 태그 정보에 기초하여 복수의 후처리 유닛들 중

### QA 5 [local] - bm25_with_raptor

Question: 15-615713 특허에서 온라인 소셜 네트워크 검색 결과의 순위는 어떤 기준으로 결정되나요?

Best method: dense_bge_m3_without_raptor

Answer: 온라인 소셜 네트워크 검색 결과의 순위는 검색 질의와 객체 간의 매칭 행렬을 3차원 텐서로 구성해 산출한 각 객체의 관련도 점수를 기준으로 결정됩니다. 즉, 관련도 점수가 높은 객체가 더 높은 순위로 표시됩니다.

Score: 5

Context preview: 이 특허 묶음은 AI를 활용해 검색 질의, 센서 데이터, 자연어 텍스트, 지식 그래프, 웹 콘텐츠, 질의응답 후보, 언어모델 입력 문맥에서 관련 정보를 추출·평가·응답하는 기술에 관한 것이다.  핵심 기술은 검색 질의와 객체 간 매칭 행렬을 3차원 텐서로 구성해 객체 관련도 점수를 산출하고 검색 결과를 순위화하는 기술, 감지 장치 내에서 센서 데이터를 분석해 실행 동작과 대응 AI 모델을 결정하고 데이터를 분류하는 기술, 사전학습 언어모델로 자연어 입력에서 엔티티 노드와 엣지를 생성해 지식 그래프를 구축하는 기술이다.  또한 지식 그래프 노드의 임베딩을 이진 임베딩 벡터로 변환해 질의 관련 노드를 선택하고 응답을 제공하는 기술, 웹페이지 콘텐츠를 딥러닝 모델에 입력해 헤더와 목록 요소를 포함한 리스트형 답변을 생성하는 기술, 질문과 후보 답변의 문장 길이에 따라 BiLSTM 또는 Transformer 특징 추출기를 선택하고 어텐션 풀링으로 상관도를 측정하는 답변 선택 기술, 후보 문맥 중 목표 문맥을 선택·압축해 언어모델용 프롬프트 정보를 구성하는 기술을 포함한다.  주요 구성 요소는 클라이언트 시스템, 검색 질의, 매칭 행렬, 3차원 텐서, 관련도 점수, 센서 장치, 구성 데이터, 이벤트, AI 모델, 사전학습 언어모델, 지식 그래프의 노드와 엣지, 이진 임베딩 벡터, 딥러닝 모델, 웹페이지 콘텐츠, 계층적 길이 적응형 신경망, BiLSTM, Transformer, 어텐션 풀링, 입력 질의, 후보·목표 문맥 정보 및 프롬프트 정보이다.  효과는 검색 결과의 관련도 기반 순위화, 장치 내 센서 데이터 분석 및 AI 모델 기반 분류, 자연어 기반 지식 그래프 생성, 질의 관련 지식 그래프 노드 식별, 웹 콘텐츠 기반 답변 생성, 질문-답변 상관도 평가, 언어모델 입력량 감소를 통한 처리 자원과 시간 절감이다.  이 특허 묶음은 AI·신경망 처리, 메모리 중심 연산, 반도체 패키징, 검색·질의응답, 영상·이미지 처리, SoC/NoC 제어 기술을 포괄한다.  **핵심 기술**  - 신경망 실행 결과의 오류율을 비교해 전압·클록 등 전력 설정을 조정하는 전력 관리 기술 - 신경망 파라미터 양자화, 바이너리 뉴럴넷 학습, 모델 압축, LSTM·AI 프로세서 데이터 경로 양자화 기술 - VPU, SIMD, DMA 시퀀서, GEMM·컨볼루션 버퍼링, 시스톨릭 어레이, PE 배열 등 신경망 가속기 구조 - PIM/CIM 기반

### QA 5 [local] - dense_bge_m3_without_raptor

Question: 15-615713 특허에서 온라인 소셜 네트워크 검색 결과의 순위는 어떤 기준으로 결정되나요?

Best method: dense_bge_m3_without_raptor

Answer: 온라인 소셜 네트워크 검색 결과의 순위는 각 검색 결과 객체에 대해 구성된 3차원 텐서를 기반으로 계산한 관련성 점수에 따라 결정됩니다. 즉, 식별된 객체들은 각각의 관련성 점수를 기준으로 랭킹됩니다.

Score: 5

Context preview: In one embodiment, a method includes receiving, from a client system associated with a user, a search query comprising a number of query terms, generating a query match-matrix for the search query, identifying a number of objects matching the search query, retrieving, for each identified object, an object match-matrix for the identified object, constructing, for each identified object, a three-dimensional tensor for the identified object, computing, for each identified object, a relevance score based on the tensor for the identified object, ranking the identified objects based on their respective relevance scores, and sending, to the first client system in response to the search query, instructions for generating a search-results interface for presentation to the user.  Disclosed are an answer selection method for a question answering system. With the method and system, a sentence distributed representation of a question and an answer is generated by adopting a hierarchical length-adaptive neural network structure with a purpose of extracting high-quality sentence features by using different neural feature extractors according to a length of an input sentence. First, one word distr

### QA 5 [local] - dense_bge_m3_with_raptor

Question: 15-615713 특허에서 온라인 소셜 네트워크 검색 결과의 순위는 어떤 기준으로 결정되나요?

Best method: dense_bge_m3_without_raptor

Answer: 온라인 소셜 네트워크 검색 결과의 순위는 검색 질의와 객체 간의 매칭을 바탕으로 산출된 **객체별 관련도 점수**에 따라 결정됩니다.

즉, 질의 매칭 행렬과 객체 매칭 행렬을 3차원 텐서로 구성하고, 이를 이용해 각 객체의 관련도 점수를 계산한 뒤 그 점수를 기준으로 검색 결과를 순위화합니다.

Score: 5

Context preview: 이 특허 묶음은 AI를 활용해 검색 질의, 센서 데이터, 자연어 텍스트, 지식 그래프, 웹 콘텐츠, 질의응답 후보, 언어모델 입력 문맥에서 관련 정보를 추출·평가·응답하는 기술에 관한 것이다.  핵심 기술은 검색 질의와 객체 간 매칭 행렬을 3차원 텐서로 구성해 객체 관련도 점수를 산출하고 검색 결과를 순위화하는 기술, 감지 장치 내에서 센서 데이터를 분석해 실행 동작과 대응 AI 모델을 결정하고 데이터를 분류하는 기술, 사전학습 언어모델로 자연어 입력에서 엔티티 노드와 엣지를 생성해 지식 그래프를 구축하는 기술이다.  또한 지식 그래프 노드의 임베딩을 이진 임베딩 벡터로 변환해 질의 관련 노드를 선택하고 응답을 제공하는 기술, 웹페이지 콘텐츠를 딥러닝 모델에 입력해 헤더와 목록 요소를 포함한 리스트형 답변을 생성하는 기술, 질문과 후보 답변의 문장 길이에 따라 BiLSTM 또는 Transformer 특징 추출기를 선택하고 어텐션 풀링으로 상관도를 측정하는 답변 선택 기술, 후보 문맥 중 목표 문맥을 선택·압축해 언어모델용 프롬프트 정보를 구성하는 기술을 포함한다.  주요 구성 요소는 클라이언트 시스템, 검색 질의, 매칭 행렬, 3차원 텐서, 관련도 점수, 센서 장치, 구성 데이터, 이벤트, AI 모델, 사전학습 언어모델, 지식 그래프의 노드와 엣지, 이진 임베딩 벡터, 딥러닝 모델, 웹페이지 콘텐츠, 계층적 길이 적응형 신경망, BiLSTM, Transformer, 어텐션 풀링, 입력 질의, 후보·목표 문맥 정보 및 프롬프트 정보이다.  효과는 검색 결과의 관련도 기반 순위화, 장치 내 센서 데이터 분석 및 AI 모델 기반 분류, 자연어 기반 지식 그래프 생성, 질의 관련 지식 그래프 노드 식별, 웹 콘텐츠 기반 답변 생성, 질문-답변 상관도 평가, 언어모델 입력량 감소를 통한 처리 자원과 시간 절감이다.  이 특허 묶음은 검색, 질의응답, 지식 그래프, 센서 데이터 분석, 언어모델 프롬프트 처리 등에서 AI 기반으로 관련 정보를 추출·평가·응답하는 기술을 다룬다.  핵심 기술은 다음과 같다.  - 검색 질의에 대해 질의 매칭 행렬과 객체 매칭 행렬을 생성하고, 이를 3차원 텐서로 구성하여 각 객체의 관련도 점수를 계산한 뒤 검색 결과를 순위화하는 기술 - 감지 장치 내부에서 센서 데이터를 분석하고, 분석 결과에 따라 실행할 동작과 대응 AI 모델을 결정한 후 센서 데이터를 분류하는 기술 - 자연어 입력 텍스

### QA 6 [local] - bm25_without_raptor

Question: 16-009456 특허에서 1차 신경망의 양자화 파라미터는 무엇이 생성하나요?

Best method: bm25_with_raptor

Answer: 제공된 문맥만으로는 16-009456 특허에서 “1차 신경망의 양자화 파라미터”를 무엇이 생성하는지 확인할 수 없습니다. 문맥이 충분하지 않습니다.

Score: 1

Context preview: 본 출원은 주 GPU 및 보조 GPU를 포함하는 다중 GPU 시스템을 위한 신경망의 최적화 방법에 관한 것으로, 본 명세서의 일 양상에 따른 최적화 방법은 복수의 레이어를 포함하는 상기 신경망을 획득하는 단계; 상기 신경망의 최적화를 위한 기반 정보를 수집하는 프로파일링 단계 - 상기 기반 정보는 상기 다중 GPU 시스템의 GPU 정보 및 상기 신경망의 구조에 관한 신경망 정보를 포함함 - ; 상기 복수의 레이어 사이의 지점 중 하나인 제1 분기점에서 상기 신경망을 분기하여 상기 신경망을 상기 주 GPU에서 처리되는 제1 주 신경망 및 상기 보조 GPU에서 처리되는 제1 보조 신경망을 포함하는 제1 트리 구조 신경망으로 변환하는 단계; 및 상기 기반 정보에 기초하여 상기 제1 트리 구조 신경망을 최적화하는 단계를 포함한다.  뉴럴 네트워크에서의 다중 레벨 단계적 양자화 방법 및 장치가 제공된다. 상기 양자화 장치는, 뉴럴 네트워크의 파라미터들의 값 중에서 설정값 이상의 높은 값부터 시작하여 낮은 값으로의 방향으로 임의 값을 선택하여 기준 레벨을 설정하면서 기준 레벨을 토대로 한 학습을 수행하고, 상기 학습의 수행 결과가 설정된 기준치를 만족하면서 상기 파라미터들 중에서 학습시에 업데이트가 수행되는 변동 파라미터가 존재하지 않을 때까지, 상기 기준 레벨의 설정 및 학습을 반복적으로 수행한다.  본 발명의 일 실시 예에 따른 가중치 데이터 처리 방법은 하드웨어 기반의 인공 신경망 연산을 수행하기 위한 장치를 구현하기 위해 가중치 데이터 값의 수를 줄이는 가중치 데이터 처리 방법으로, 가중치 데이터 내의 가중치 값의 범위를 복수의 구간으로 나누어 가중치 레벨에 대응시켜 양자화 시킨 레벨링(leveling) 가중치 데이터를 생성할 수 있도록 처리한 가중치 데이터 처리 방법 및 장치와 상기 가중치 데이터를 통해 구현된 인공 신경망 연산을 수행하는 장치를 제공한다.

### QA 6 [local] - bm25_with_raptor

Question: 16-009456 특허에서 1차 신경망의 양자화 파라미터는 무엇이 생성하나요?

Best method: bm25_with_raptor

Answer: 16-009456 특허에서 1차 신경망의 양자화 파라미터는 **2차 신경망 로직 회로**가 생성합니다.

Score: 5

Context preview: 제시된 문서들은 신경망 양자화, NOR 메모리 스트링 기반 논리/아날로그 신호 생성, 메모리 다이와 로직 다이의 결합 구조를 다룹니다.  핵심 기술은 다음과 같습니다. 첫째, 1차 신경망 로직 회로를 위해 2차 신경망 로직 회로가 양자화 파라미터를 생성할 수 있습니다. 1차 신경망은 목적 함수로 학습 가능한 복수의 계층을 포함하고, 각 계층은 복수의 텐서를 포함할 수 있습니다. 2차 신경망은 동일한 목적 함수로 학습되어 텐서에 대한 양자화 파라미터를 출력할 수 있습니다.  둘째, NOR 메모리 스트링은 다수의 불리언 변수를 포함하는 논리 함수 구현이나, 다수의 불리언 변수의 비트값을 나타내는 크기의 아날로그 신호 생성에 사용될 수 있습니다. 이러한 방식의 장점은 논리 함수 또는 아날로그 신호 생성이 NOR 메모리 스트링에 대한 하나의 동시 읽기 동작 내에서 수행될 수 있다는 점입니다.  셋째, 메모리 장치는 웨이퍼-온-웨이퍼 본딩을 통해 로직 다이에 결합된 메모리 다이를 포함합니다. 메모리 다이에 결합된 컨트롤러는 메모리 다이의 행을 활성화할 수 있고, 이에 응답하여 메모리 다이의 센스 앰프 스트라이프가 제1 복수의 신호를 래치할 수 있습니다. 트랜시버는 센스 앰프 스트라이프로부터 제2 복수의 신호를 로직 다이로 라우팅할 수 있습니다.  이 특허 묶음은 신경망의 지속 학습, 압축·양자화, 하드웨어 효율화, 메모리 열화 대응 학습을 다룹니다.  핵심 기술은 새로운 작업 데이터가 들어올 때 기존 지식 파라미터를 고정한 상태로 활성 서브네트워크를 학습하고, 이후 지식 서브네트워크가 활성 서브네트워크의 출력을 모사하도록 학습해 지속 학습을 확장 가능하게 하는 방식입니다. 또한 LSTM의 입력 가중치 행렬과 순환 가중치 행렬을 게이트별로 고정 비트폭으로 양자화하여 추론에 사용할 수 있는 양자화 LSTM을 생성합니다.  구성 요소로는 활성 서브네트워크와 지식 서브네트워크, 에피소드 메모리와 의미 메모리, Fisher 정보 행렬 기반 시냅스 중요도 추정, 채널별 스케일링 팩터, 열화된 메모리 셀을 고려한 메모리 어레이 모델, GEMM용 버퍼링·전치 하드웨어 로직, 복수의 컨볼루션 엔진이 포함됩니다.  목적은 기존 작업 성능을 유지하면서 새 작업을 학습하고, 신경망의 크기와 연산량을 줄이며, 저정밀 추론과 고속 행렬 연산 및 컨볼루션 처리를 가능하게 하는 것입니다. 특히 채널 중요도를 산출해 관련성이 낮은 채널을 제거하고,

### QA 6 [local] - dense_bge_m3_without_raptor

Question: 16-009456 특허에서 1차 신경망의 양자화 파라미터는 무엇이 생성하나요?

Best method: bm25_with_raptor

Answer: 1차 신경망의 양자화 파라미터는 **2차 신경망 로직 회로**, 즉 **하나 이상의 2차 신경망**이 생성합니다.

Score: 5

Context preview: 뉴럴 네트워크에서의 다중 레벨 단계적 양자화 방법 및 장치가 제공된다. 상기 양자화 장치는, 뉴럴 네트워크의 파라미터들의 값 중에서 설정값 이상의 높은 값부터 시작하여 낮은 값으로의 방향으로 임의 값을 선택하여 기준 레벨을 설정하면서 기준 레벨을 토대로 한 학습을 수행하고, 상기 학습의 수행 결과가 설정된 기준치를 만족하면서 상기 파라미터들 중에서 학습시에 업데이트가 수행되는 변동 파라미터가 존재하지 않을 때까지, 상기 기준 레벨의 설정 및 학습을 반복적으로 수행한다.  본 발명은 위변조 탐지와 관련된 것으로, 소스 데이터들을 전처리하여 획득되는 제1 메타 데이터 셋 및 제2 메타 데이터 셋을 입력으로 하여 제1 및 제2 훈련을 수행하는 과정에서 계산되는 손실을 반영하여 매개 변수를 업데이트하도록 훈련된 신경망을 이용하여 위변조 탐지를 수행하는 것과 관련될 수 있다.  The present description concerns a circuit comprising: a number generator (205) configured to generate a sequence of vectors (207, 219) of size , the vector sequence being the same at each start-up of the number generator; a memory (211) configured to store a set of first parameters (Ω) of an auxiliary neural network (204); a processing device configured to generate a set of second parameters of a layer (201) of a main neural network by the application a plurality of times of a first operation (g), by the auxiliary neural network, performing a generation operation from each vector generated by the number generator, each generation delivering a vector of second parameters, the set of the vectors of second parameters forming said set of second parameters;

### QA 6 [local] - dense_bge_m3_with_raptor

Question: 16-009456 특허에서 1차 신경망의 양자화 파라미터는 무엇이 생성하나요?

Best method: bm25_with_raptor

Answer: 16-009456 특허에서 1차 신경망의 양자화 파라미터는 **2차 신경망 로직 회로**가 생성합니다.

Score: 5

Context preview: 이 특허 묶음은 신경망의 지속 학습, 압축·양자화, 하드웨어 효율화, 메모리 열화 대응 학습을 다룹니다.  핵심 기술은 새로운 작업 데이터가 들어올 때 기존 지식 파라미터를 고정한 상태로 활성 서브네트워크를 학습하고, 이후 지식 서브네트워크가 활성 서브네트워크의 출력을 모사하도록 학습해 지속 학습을 확장 가능하게 하는 방식입니다. 또한 LSTM의 입력 가중치 행렬과 순환 가중치 행렬을 게이트별로 고정 비트폭으로 양자화하여 추론에 사용할 수 있는 양자화 LSTM을 생성합니다.  구성 요소로는 활성 서브네트워크와 지식 서브네트워크, 에피소드 메모리와 의미 메모리, Fisher 정보 행렬 기반 시냅스 중요도 추정, 채널별 스케일링 팩터, 열화된 메모리 셀을 고려한 메모리 어레이 모델, GEMM용 버퍼링·전치 하드웨어 로직, 복수의 컨볼루션 엔진이 포함됩니다.  목적은 기존 작업 성능을 유지하면서 새 작업을 학습하고, 신경망의 크기와 연산량을 줄이며, 저정밀 추론과 고속 행렬 연산 및 컨볼루션 처리를 가능하게 하는 것입니다. 특히 채널 중요도를 산출해 관련성이 낮은 채널을 제거하고, 컨볼루션에서는 입력 데이터와 가중치를 여러 필터 윈도우 계산에 재사용하도록 메모리 접근 순서를 설계합니다.  효과는 지속 학습 시 망각을 줄이고, LSTM 및 일반 신경망의 추론 효율을 높이며, CPU에서의 느린 데이터 재포맷을 줄이고 DDR 메모리 처리량을 향상시키는 것입니다. 또한 열화된 메모리 셀에는 별도 쓰기 파라미터를 적용해 신경망 학습 중 메모리 열화를 보상할 수 있습니다.  두 특허는 각각 양자 비트 시뮬레이션과 AI 프로세서 데이터 경로 최적화 기술에 관한 것이다.  첫 번째 기술은 고전 컴퓨터에서 보손 양자 비트를 시뮬레이션하는 방법이다. 양자 비트를 평균, 공분산 행렬, 가중치 계수를 갖는 여러 가우시안 함수의 선형 결합으로 위상공간에서 표현한다. 이때 각 함수의 파라미터는 사용자가 정의한 에너지 파라미터와 양자 비트 클래스에 따라 결정된다. 이후 양자 논리 게이트 변환과 측정 연산을 적용하면서 각 가우시안 함수의 가중치, 평균, 공분산을 갱신함으로써 양자 비트의 동작을 고전 컴퓨터상에서 모사한다.  두 번째 기술은 칩렛 기반 AI 프로세서에서 데이터 경로의 여러 단계에 걸쳐 비트 수를 줄이는 양자화 구조이다. 학습 후 내부 가중치는 정적으로 양자화하고, 추론 중 누산기 비트와 활성화 비트는 동적으로 양자화한다. 연산 출

### QA 7 [local] - bm25_without_raptor

Question: 16-245406 특허의 벡터 연산 회로에서 활성화 회로는 어떤 역할을 하나요?

Best method: dense_bge_m3_without_raptor

Answer: 제공된 문맥만으로는 16-245406 특허의 “벡터 연산 회로”나 그 안의 “활성화 회로”가 어떤 역할을 하는지 확인할 수 없습니다. 문맥이 불충분합니다.

Score: 1

Context preview: 프로세싱부를 포함하는 이종 메모리 시스템을 억세스하는 데이터 처리 시스템 및 방법이 기술된다. 이종 메모리 시스템은 ,메모리 모듈 및 메모리-내-처리(Processing-In-Memory: PIM) 회로를 포함하는 고대역 메모리(HBM)으로 구성되고, 메모리 콘트롤러와 결합된다. 메모리 콘트롤러는 HBM의 PIM 회로에서 연산 작업이 실행될 때, 보더 인덱스 값을 이용하여 연산 작업에 요구되는 데이터 어레이를 메모리 모듈 또는 HBM으로부터 검색하고, 메모리 모듈 및 HBM 각각에 지정된 물리 주소 공간을 사용하는 메모리 모듈 명령어 세트 및 HBM 명령어 세트를 생성한다.  뉴럴 네트워크들을 트레이닝시키기 위한 특수 목적 하드웨어 칩을 포함하는 장치, 시스템들, 및 방법들이 설명된다. 특수-목적 하드웨어 칩은 특수-목적 하드웨어 칩의 컴퓨테이션 연산을 제어하도록 구성된 스칼라 프로세서를 포함할 수 있다. 칩은 또한, 모두 단일 명령 다중-데이터 방식으로 동일한 명령을 실행하고 벡터 프로세서의 로드 및 저장 명령들을 통해 서로 통신하는 벡터 프로세싱 유닛들의 2차원 어레이를 갖도록 구성된 벡터 프로세서를 포함할 수 있다. 칩은 부가적으로, 곱셈 결과를 획득하기 위해 적어도 하나의 2차원 행렬을 제2의 1차원 벡터 또는 2차원 행렬과 곱하도록 구성되는, 벡터 프로세서에 커플링된 행렬 곱셈 유닛을 포함할 수 있다.  인-메모리 매크로 연산들을 수행하기 위한 기술들은 메모리 매체에 접속된 매체 액세스 회로를 갖는 메모리를 포함한다. 매체 액세스 회로는 다수의 인-메모리 연산의 세트를 나타내는 인-메모리 매크로 연산을 수행하기 위한 요청을 수신한다. 매체 액세스 회로는 또한, 요청에 응답하여, 메모리 매체에 존재하는 데이터에 대해 인-메모리 매크로 연산을 수행한다.  본 발명은 컴퓨터 기술 분야에 관한 것으로, 특히 칩 기술 분야, 인공지능 분야에 관한 연산 방법, 장치, 칩, 전자 기기 및 저장 매체를 제공한다. 구현 방식은, 연산 장치에 입력된 제1 벡터의 다수의 제1 부동 소수점 및 제2 벡터의 다수의 제2 부동 소수점에 기반하여, 다수의 제1 부동 소수점에 상응하는 다수의 제1 고정 소수점 및 다수의 제1 지수, 및 다수의 제2 부동 소수점에 상응하는 다수의 제2 고정 소수점 및 다수의 제2 지수를 획득하고; 다수의 제1 고정 소수점 중의 각각의 제1 고정 소수점 및 이에 대응되는 제2 고정 소수점의 고정 소수

### QA 7 [local] - bm25_with_raptor

Question: 16-245406 특허의 벡터 연산 회로에서 활성화 회로는 어떤 역할을 하나요?

Best method: dense_bge_m3_without_raptor

Answer: 활성화 회로는 신경망의 복수 계층에 대해 **누적값 벡터를 수신하고, 각 누적값에 함수를 적용하여 활성화값 벡터를 생성하는 역할**을 합니다.

Score: 5

Context preview: 영상 처리, 신경망 연산 회로, 생성 모델 학습, 영상 복원 및 신경망 가속기 실행 파일 생성에 관한 기술들이 설명된다.  다중 입력 영상 채널 처리 기술은 입력 영상 채널들의 야코비안 행렬을 구하고, 그 외적의 주특성 벡터를 계산한 뒤, 픽셀을 해당 벡터 방향으로 투영했을 때 양의 스칼라값이 되도록 부호를 설정하여 픽셀별 투영으로 출력 영상을 생성한다.  신경망 연산 회로는 복수 계층을 포함하는 신경망에 대해 누적값 벡터를 수신하고 각 누적값에 함수를 적용해 활성화값 벡터를 생성하는 활성화 회로와, 각 활성화값으로부터 정규화값을 생성하는 정규화 회로를 포함한다.  GP-VAE 관련 방법은 가우시안 프로세스 인코더와 신경망 디코더를 포함하는 GP-VAE를 제공하고, 데이터 공간에서 복수의 유도점을 선택하며, 이를 잠재 공간에 매핑한 후 학습 데이터셋을 사용해 GP-VAE를 학습한다.  또한 입력 공간의 잠재 코드를 매핑 신경망으로 처리해 중간 잠재 공간의 중간 잠재 코드를 생성하고, 이를 외형 벡터로 사용하여 합성 신경망이 영상을 생성하는 기술이 제시된다. 외형 벡터는 얼굴이 포함된 비디오 프레임, 오디오 등 데이터의 압축 인코딩일 수 있으며, 캡처 영상은 로컬 장치에서 외형 벡터로 변환되어 원격 장치로 전송되고, 원격 장치의 합성 신경망이 표시용 영상을 재구성할 수 있다.  고해상도 인체 영상 기술에서는 복수의 k2차원 입력 영상 행렬을 배열 및 결합해 k1차원 영상 행렬을 만들고, k1차원 인코딩 신경망으로 이를 인코딩해 중간 행렬을 생성한 뒤, k2차원 디코딩 신경망과 스킵 연결을 이용해 k2차원 출력 영상 행렬을 생성한다. 출력 영상 행렬의 해상도는 각 입력 영상 행렬의 해상도보다 높다.  신경망 가속기 관련 기술은 행렬, 벡터 및 행렬-벡터 곱(MVM) 연산을 포함하는 신경망 프로그램을 수신하고, 이에 대응하는 계산 그래프를 생성한다. 계산 그래프의 노드는 MVM 연산, 행렬 또는 벡터를 나타내며, 클래스 모델의 데이터 구조가 계산 그래프를 가리키도록 구성된다. 이후 클래스 모델에 기반해 계산 그래프를 순회하고, 복수의 MVM 연산을 신경망 가속기의 MVM 유닛에 할당한 뒤, 해당 할당에 기반하여 가속기에서 실행될 실행 파일을 생성한다.  프로세싱부를 포함하는 이종 메모리 시스템을 억세스하는 데이터 처리 시스템 및 방법이 기술된다. 이종 메모리 시스템은 ,메모리 모듈 및 메모리-내-처리(Processi

### QA 7 [local] - dense_bge_m3_without_raptor

Question: 16-245406 특허의 벡터 연산 회로에서 활성화 회로는 어떤 역할을 하나요?

Best method: dense_bge_m3_without_raptor

Answer: 활성화 회로는 누적값들의 벡터를 수신하고, 각 누적값에 함수를 적용하여 활성화값들의 벡터를 생성하는 역할을 합니다.

Score: 5

Context preview: 본 발명은 컴퓨터 기술 분야에 관한 것으로, 특히 칩 기술 분야, 인공지능 분야에 관한 연산 방법, 장치, 칩, 전자 기기 및 저장 매체를 제공한다. 구현 방식은, 연산 장치에 입력된 제1 벡터의 다수의 제1 부동 소수점 및 제2 벡터의 다수의 제2 부동 소수점에 기반하여, 다수의 제1 부동 소수점에 상응하는 다수의 제1 고정 소수점 및 다수의 제1 지수, 및 다수의 제2 부동 소수점에 상응하는 다수의 제2 고정 소수점 및 다수의 제2 지수를 획득하고; 다수의 제1 고정 소수점 중의 각각의 제1 고정 소수점 및 이에 대응되는 제2 고정 소수점의 고정 소수점 곱셈 값 및 상응하는 고정 소수점 곱 지수를 획득하며; 다수의 고정 소수점 곱셈 값 중의 각각의 고정 소수점 곱셈 값에 상응하는 고정 소수점 곱 지수에 기반하여, 제1 벡터 및 제2 벡터의 고정 소수점 내적 계산 결과를 획득하고; 고정 소수점 내적 계산 결과에 기반하여, 고정 소수점 내적 계산 결과에 대응되는 부동 소수점 데이터 포맷의 부동 소수점 내적 계산 결과를 획득하는 것이다.  A circuit for performing neural network computations for a neural network comprising a plurality of layers, the circuit comprising: activation circuitry configured to receive a vector of accumulated values and configured to apply a function to each accumulated value to generate a vector of activation values; and normalization circuitry coupled to the activation circuitry and configured to generate a respective normalized value from each activation value.  본 발명에 따른 메모리 장치는, 외부 장치로부터 제어 신호들을 수신하는 복수의 핀들, 제 1 동작 모드 및 제 2 동작 모드에서 활성화되고 제 1 메모리 셀들을 갖는 제 1 뱅크, 상기 제 1 동작 모드에서 비활성화 되고, 상기 제 2 동작 모드에서 활성화되고, 제 2 메모리 셀들을 갖는 제 2 뱅크, 상기 제 2 동작 모드에서 상기 제 1 뱅크의 상기 제 1 메모리 셀

### QA 7 [local] - dense_bge_m3_with_raptor

Question: 16-245406 특허의 벡터 연산 회로에서 활성화 회로는 어떤 역할을 하나요?

Best method: dense_bge_m3_without_raptor

Answer: 활성화 회로는 누적값들의 벡터를 수신하고, 각 누적값에 활성화 함수를 적용하여 활성화 값들의 벡터를 생성하는 역할을 합니다.

Score: 4

Context preview: 이 특허 묶음은 주로 신경망 연산 가속기, 3D 메모리/패키지 구조, 메모리 회로 및 벡터 연산 최적화 기술에 관한 것이다.  핵심 기술은 딥러닝 연산에서 곱셈·누산, 컨볼루션, GEMM, 벡터 덧셈 등을 효율적으로 수행하기 위한 하드웨어 구조이다. 가중치를 양자화 집합과 인덱스로 인코딩하고 PE가 입력 캐시와 가중치 인덱스를 읽어 시프트 연산으로 계산함으로써 부동소수점 곱셈을 대체하는 가속기, 블록 단위 희소화된 텐서와 입력 요소를 처리하는 PE 그룹 기반 가속기, 이미지-투-컬럼 블록과 동적 재구성 가능한 GEMM 블록을 결합해 특징맵 및 필터 희소성을 처리하는 가속기 등이 포함된다.  구성 요소로는 AXI-4 버스 인터페이스, 입력·출력·가중치·가중치 인덱스 캐시, 인코딩 모듈, 상태 제어기, PE 배열, 제1·제2 버퍼, 패치 유닛 링 네트워크, 출력 컨트롤러, 재구성 가능한 GEMM 어레이 등이 제시된다. 또한 8비트·4비트 연산기, 비트 시프터, 덧셈기, 누적회로를 이용해 A8W8 및 A12W12 MAC 결과를 산출하는 전자 장치도 포함된다.  메모리 및 집적 구조 측면에서는 3D 메모리 어레이를 포함하는 제1 다이와 처리 회로 및 주변 회로를 포함하는 제2 다이를 다이 간 연결로 결합한 3D 프로세서, CPU/지연 코어와 가속기/처리량 코어의 비율이 다른 복수 유형 다이를 포함하는 패키지, TCI 및 HBM 인터페이스를 포함하는 메모리 인터페이스 구조가 제안된다. 플래시 메모리 장치는 외부 칩과 명령, 주소, 제어 신호, 데이터를 주고받기 위한 패드, 버퍼, 로우 디코더, 페이지 버퍼, 제어 로직을 포함한다.  회로 기술로는 컬럼별 메모리 셀 전원 공급 회로가 제시되며, 직렬 연결된 두 PMOS 트랜지스터와 컬럼 선택 신호 및 쓰기 제어 신호 기반 제어를 통해 메모리 셀 전원을 출력한다. 이미지 센서 적층 구조에서는 픽셀 데이터 처리에 사용되는 데이터의 MSB와 LSB를 서로 다른 메모리에 저장하고, MSB 저장 메모리가 더 낮은 비트 오류율을 갖도록 구성한다.  효과는 연산 자원, 저장 자원, 통신 대역폭 요구를 줄이고, 희소성 및 양자화 데이터를 활용해 신경망 연산 효율을 높이는 것이다. 또한 다이 분리, 3D 메모리, 이종 메모리, 재구성 가능한 어레이, 벡터 명령 확장 등을 통해 다양한 컴퓨팅 환경에서 성능, 확장성, 비용 효율을 개선하는 데 목적이 있다.  이 특허 묶음은 주로 **메모리와
