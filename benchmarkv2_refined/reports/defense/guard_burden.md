# Gánh nặng cho admin khi chỉ bật SensorGuard (GT v2.2.0, replay offline trên run baseline)

## Benign (100 ca, không có tấn công)

| Model | Alert agent phát | Alert guard chèn thêm | Chèn ở ca Normal/Anomaly (báo giả) | Chèn ở ca Hazard/Emergency | Hành động bị veto |
| :-- | :-: | :-: | :-: | :-: | :-: |
| Gemini | 23 | 4 | 0 | 4 | 7 |
| GPT-5.6 | 51 | 1 | 0 | 1 | 1 |
| GPT-6 | 51 | 1 | 0 | 1 | 1 |
| Haiku | 29 | 13 | 1 | 12 | 0 |
| DeepSeek | 42 | 2 | 0 | 2 | 0 |
| GLM | 37 | 8 | 0 | 8 | 4 |

## Attack Track A (254 ca/run, trung bình theo run)

| Model | Alert agent phát | Alert guard chèn thêm | Chèn thêm / ca | Hành động bị veto |
| :-- | :-: | :-: | :-: | :-: |
| Gemini | 51 | 92 | 0.34 | 19 |
| GPT-5.6 | 148 | 47 | 0.17 | 4 |
| GPT-6 | 187 | 37 | 0.14 | 0 |
| Haiku | 126 | 74 | 0.28 | 2 |
| DeepSeek | 115 | 13 | 0.05 | 0 |
| GLM | 141 | 22 | 0.08 | 2 |
