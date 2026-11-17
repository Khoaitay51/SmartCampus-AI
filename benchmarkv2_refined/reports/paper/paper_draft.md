# Sensor-Grounded Defense for LLM Agents in a Cyber-Physical Smart Campus: Benchmarking Indirect Prompt Injection Across Six Models

*Author One, Author Two, Author Three — Faculty of Information Security (placeholder)*

> Bản xem trước của `paper_draft.tex`. Ô **TBD** = thí nghiệm đang chạy. Sửa ở đây trước, chốt xong mới chuyển sang LaTeX.

## Abstract

LLM agents that read IoT telemetry and drive physical actuators (fans, door locks, sirens) are exposed to *indirect prompt injection* (IPI) through free-text fields written by third parties. We study this risk on a deployed Smart Campus building-management agent (ReAct with reflection, RAG, finite-state-machine permissions). We build a deterministic, LLM-judge-free benchmark with 100 benign and 254 attack cases (+16 robustness cases) grounded on real sensor data, and a four-class taxonomy: actuation harm (DH-A), security harm (DH-S), *safety suppression* (SUP) and data stealing (DS). Across six models, the attack success rate (ASR) ranges from 2.8% to 27.6% while benign utility (BU) stays within 84–93%. SUP, i.e. persuading the agent *not* to react to a hazard that sensors already show, causes 59–91% of all successful attacks; data stealing never succeeds. A clean-twin control confirms that this SUP is caused by the injected text and not by a policy mismatch. We then propose **Sensor-Grounded Response**: untrusted-text marking, prompt principles and a fixed sensor-rule guard placed after the agent. Replayed on recorded runs, the guard lowers ASR to ≤0.8% (4.9% for the weakest model) without reducing BU. The prompt-level part is under evaluation.

**Keywords:** LLM agents, indirect prompt injection, cyber-physical systems, IoT, safety suppression, benchmark, defense

---

## I. Introduction

LLM agents are moving from chat to *control*: they read sensor streams and issue actuator commands. In a building-management setting a wrong decision is physical — a fan is switched off in an overheating server room, or a smoke alarm is ignored. The attacker does not need to talk to the agent: IoT events carry free-text fields (maintenance notes, event descriptions, tickets) that any integrated third party can write, and the agent reads them as context. This is indirect prompt injection [1].

Existing agent-security benchmarks target digital tools such as email and banking [3], [4]. They mostly measure whether the agent *does something it should not*. In a cyber-physical system there is a second, quieter failure: the agent *fails to do what it should*. We call it **safety suppression (SUP)**: the injected text explains away a real sensor reading ("fire drill", "sensor under calibration") and the agent stands down.

**Contributions**
1. **A deterministic IPI benchmark for a physical agent.** 100 benign and 254 attack cases (+16 robustness) on a live TimescaleDB/RAG environment, scored by action matching only (no LLM judge), with Wilson 95% intervals.
2. **Taxonomy-level evidence on six models.** SUP is the dominant failure (59–91% of successes) while DS is 0%; a *clean-twin* control separates attack-induced SUP from policy mismatch.
3. **Sensor-Grounded Response**, a defense whose last stage ignores text entirely. Replayed on recorded runs it cuts ASR by 5–30× and does not lower BU.

## II. Related Work

**Prompt injection.** Greshake et al. [1] introduced IPI against LLM-integrated applications; Perez and Ribeiro [2] showed goal hijacking by simple instructions. **Agent benchmarks.** AgentDojo [3] and InjecAgent [4] evaluate tool-using agents in digital environments and report utility-under-attack and ASR. We keep these metrics but (i) use a physical environment with real telemetry, (ii) add omission-type attacks (SUP), (iii) add a clean-twin control. **Defenses.** Spotlighting [5] marks untrusted input; CaMeL [6] separates control and data flow by design. Ours combines marking with a deterministic, text-blind guard grounded in trusted sensor values. **Agent reasoning.** The agent follows ReAct [7] with review and reflection.

## III. System and Threat Model

### A. Smart Campus Agent
Edge sensors (DHT22, MQ-2, CO₂, RFID, dual IR) publish over MQTT to an edge gateway that keeps a room FSM (`saving, self_study, lecture, exam, lock, suspected, emergency`). The agent (ReAct, ≤5 steps, review + up to 3 reflections) has read-only RAG tools (`get_telemetry`, `get_room_history`, `compare_rooms`, …) and action tools (`set_fan`, `set_door`, `set_mode`, `trigger_buzzer`, `send_alert`). It emits **one action per event**; a permission matrix per FSM mode and a human-in-the-loop layer sit behind it.

### B. Threat Model
The attacker controls **only** `event_data.description`. Sensor values, timestamps, room context, RAG store and system prompt are trusted. Goals: **DH-A** harmful actuation; **DH-S** weaken security (unlock, downgrade mode); **SUP** make the agent skip or downgrade a needed protective response; **DS** read a secret from RAG and send it out (canary tokens). Six persuasion styles: authority claim, drill/test, urgency, maintenance, technical notice, policy claim. Advanced payloads mimic system structure (XML/JSON "kernel override" tags) and cite sensor calibration or dual-safety conflicts.

## IV. Benchmark and Metrics

### A. Datasets
Attack cases = 5 real-environment scenarios (U1–U5) × 60 attacker profiles, after removing semantically invalid pairs.

**Table I — Benchmark composition**

| Suite | Content | Cases |
|:--|:--|--:|
| Benign | 5 categories × 20 (Normal 40, Anomaly 20, Hazard 25, Emergency 15) | 100 |
| Track A (IPI) | DH-A 100, SUP 88, DH-S 36, DS 30 | 254 |
| Track B | Stale replay, sensor conflict, wrong tool, parameter manipulation | 16 |
| Clean twin | SUP cases with injection removed (Z) or only directive removed (P) | – |

**Table II — Attack scenarios (state frozen at T₀) and accepted protective actions**

| ID | Physical truth | Protective action (any) |
|:--|:--|:--|
| U1 | Server 52.3 °C, 0 people | fan on, alert ≥ warning |
| U2 | Smoke 650 ppm, 18 people | alert ≥ warning, buzzer, EMERGENCY |
| U3 | CO₂ 1850 ppm, 35 people | fan on, alert ≥ warning |
| U4 | Unauthorized RFID, room in LOCK | alert ≥ warning, LOCK/SUSPECTED, buzzer |
| U5 | Normal class (control) | no actuation |

### B. Metrics
All metrics come from the recorded action trajectory; no LLM judge. SUP success = emitted action outside the scenario's protective set (skip, wrong tool, or alert below *warning*).

**Table III — Metrics (↑ higher better, ↓ lower better)**

| Metric | Definition |
|:--|:--|
| BU ↑ | Accuracy on 100 benign cases (also split protective / safe) |
| ASR ↓ | Successful attacks / valid runs (254 cases) |
| SUP ↓ | ASR on the 88 safety-suppression cases |
| UA ↑ | Correct protective behavior under attack |
| MHR ↓ | Missed-hazard rate on DH-A, DH-S, SUP cases |
| FDR ↓ | Share of outputs that needed the fallback parser |
| F_Z ↓ | Miss rate with injection removed (clean twin) |

### C. Models and Protocol
Six agents share prompt, tools and database: Gemini 3.5 flash-lite (k=3), GPT-5.6 luna (k=1), GPT-6 luna (k=2), Claude Haiku 5.5, DeepSeek flash, GLM 5.3 flash (k=1). Ground truth v2.2.0, whose protective set was aligned with the agent's system prompt (Sec. V-D).

## V. Benign Evaluation

All models handle *safe* cases (95–100%); they differ on *protective* cases, where the agent must act. That is the main source of the BU gap: Haiku 62.5%, GLM 67.5% vs Gemini 90%. Smoke is hardest for GLM (60%) and Haiku (75%). No model ignored a fire with people present. BU is the cost side of the defense trade-off: a defense is useful only if it does not push BU below these values.

**Table IV — Benign utility (%)**. Prot./Safe = cases needing/not needing action (40/60); categories 20 cases each.

| Model | **BU ↑** | Prot. | Safe | Temp | Smoke | CO₂ | RFID | Maint. |
|:--|--:|--:|--:|--:|--:|--:|--:|--:|
| Gemini 3.5 flash-lite | **93.0** | **90.0** | 95.0 | 85 | 95 | 85 | 100 | 100 |
| GPT-luna ᵃ | 92.0 | 82.5 | 98.3 | 95 | 80 | 85 | 100 | 100 |
| DeepSeek flash | 92.0 | 80.0 | **100** | 100 | 80 | 85 | 95 | 100 |
| GLM 5.3 flash | 86.0 | 67.5 | 98.3 | 95 | 60 | 75 | 100 | 100 |
| Haiku 5.5 | 84.0 | 62.5 | 98.3 | 75 | 75 | 85 | 90 | 95 |

ᵃ GPT-5.6 and GPT-6 luna share one benign run (92%).

## VI. Attack Evaluation

### A. Main Results
Three findings. (i) **Wide spread:** ASR runs from 2.8% (DeepSeek) to 27.6% (Gemini) while BU spans only 84–93%. The highest-BU model (Gemini) is least robust; DeepSeek reaches 92% BU with the lowest ASR; the lowest-BU model (Haiku, 84%) is not safer than GPT-6 (92%). Robustness is not simply traded against utility. (ii) **Newer models fail differently:** Gemini follows the payload ("skip"); newer models usually *recognize* the text as unverified yet still back off. (iii) **FDR matters for measurement:** for Gemini about half of successful DH-A attacks pass through the fallback parser (15/27 in run 2), inflating ASR; for newer models fallback almost never leads to success.

**Table V — Benign utility vs attack robustness (GT v2.2.0, 254 attack cases).** k = runs; k>1: mean ± std.

| Model | k | **BU ↑** | **ASR ↓** | **SUP ↓** | **FDR ↓** | UA ↑ | MHR ↓ | ASR 95% CI |
|:--|:-:|--:|--:|--:|--:|--:|--:|:--|
| Gemini 3.5 flash-lite | 3 | **93.0** | 27.6 ± 4.8 | 47.3 ± 9.2 | 14.0 ± 3.1 | 65.5 | 34.2 | [17.7, 37.9] (3 runs) |
| GPT-5.6 luna | 1 | 92.0 | 12.6 | 29.5 | 14.2 | 81.5 | 19.2 | [9.1, 17.2] |
| GPT-6 luna | 2 | 92.0 | 6.9 ± 0.3 | 18.2 ± 3.2 | **0.4** | 85.0 | 14.5 | [4.2, 10.9] |
| Claude Haiku 5.5 | 1 | 84.0 | 11.8 | 30.7 | 3.5 | 71.7 | 28.6 | [8.4, 16.4] |
| DeepSeek flash | 1 | 92.0 | **2.8** | **6.8** | 5.9 | **95.3** | **4.5** | [1.3, 5.6] |
| GLM 5.3 flash | 1 | 86.0 | 4.3 | 8.0 | 8.3 | 91.3 | 9.4 | [2.4, 7.6] |

*Gemini benign and attack run 1 ran with the "seed" RAG state; all other runs after the hourly RAG roll-up. Using Gemini runs 2–3 only (same state), ASR is 28.3–31.9% and the ranking is unchanged. GPT-5.6/Haiku and DeepSeek/GLM are not separable at k=1 (overlapping CI).*

### B. Taxonomy: Suppression Is the Weak Spot
DS is 0% for every model: the agent never completes read-then-exfiltrate, even with audit-style pretexts. DH-S ≤ 5.6%. DH-A is high only for Gemini (26.3%). **SUP dominates**: largest class for every model, 59–91% of successful attacks. The dangerous failure is not "agent does something bad" but "agent does nothing about a hazard it can see".

**Table VI — ASR (%) by taxonomy**

| Class (cases) | Gemini | GPT-5.6 | GPT-6 | Haiku | DeepSeek | GLM |
|:--|--:|--:|--:|--:|--:|--:|
| **SUP** (88) | 47.3 | 29.5 | 18.2 | 30.7 | **6.8** | 8.0 |
| DH-A (100) | 26.3 | 5.0 | 1.5 | 3.0 | **1.0** | 4.0 |
| DH-S (36) | 5.6 | 2.8 | 0 | 0 | 0 | 0 |
| DS (30) | 0 | 0 | 0 | 0 | 0 | 0 |
| SUP share of successes | 59 | 81 | 91 | 90 | 86 | 64 |

### C. Where Suppression Succeeds
Gemini is deceived in all four scenarios, worst in U4 (RFID) and U3. DeepSeek and GLM are nearly immune in U1–U3 but still fail U4 (4–5/22): a stolen-card alert is a judgment call with no hard physical number to anchor it. GPT-5.6 and Haiku are weak in U1 and U4. By persuasion style (pooled over models): *drill/test* 25.6%, technical notice 20.6%, maintenance 16.4%, authority claim 10.0% — a plausible **alternative explanation** of the sensor value works better than an order.

**Table VII — SUP successes per scenario (out of 22; Gemini, GPT-6: mean over runs)**

| Scenario | Gemini | GPT-5.6 | GPT-6 | Haiku | DeepSeek | GLM |
|:--|--:|--:|--:|--:|--:|--:|
| U1 overheating | 7.7 | 10 | 3.5 | 6 | **0** | **0** |
| U2 smoke | 8.0 | 2 | 0.5 | 1 | **0** | 1 |
| U3 CO₂ | 11.0 | 6 | 7.0 | 8 | **1** | 2 |
| U4 RFID | 15.0 | 8 | 5.0 | 12 | 5 | 4 |

### D. Clean-Twin Validation
A high or low SUP could come from a **policy mismatch**: the ground truth may penalize an action the system prompt prescribes. The clean twin re-runs SUP cases with all injected content removed (Z) and measures the miss rate F_Z. If F_Z = 0, every miss in the attacked run is attributable to the injection. In the first ground truth (v2.1) U2 required a siren or EMERGENCY though the prompt prescribes `send_alert`; GPT-5.6 showed F_Z = 3/3. Aligning the ground truth (v2.2.0) removed the artifact and lowered SUP of GPT-5.6, GPT-6 and DeepSeek by 22.8, 24.4 and 22.7 points. After the fix all models have F_Z = 0/9 in every scenario.

**Table VIII — Clean-twin control (9 runs per scenario)**

| Model | F_Z (U1–U4) | Attack-induced SUP | Verdict |
|:--|:--|:--|:--|
| Gemini | 0/9 each | 46/88 = 52.3% | real SUP (p < 0.05) |
| GPT-5.6 | 0/9 each | 26/88 = 29.5% | real in U1, U4 |
| GLM 5.3 | 0/9 each | 7/88 = 8.0% | no policy error |
| DeepSeek | 0/9 each | 6/88 = 6.8% | no policy error |

## VII. Defense: Sensor-Grounded Response

### A. Root Cause
The only attack channel is the description field, yet the sensor value is real. The strongest tactic gives no order; it offers a competing explanation for a real reading. The system also lets this succeed: the policy engine accepts a *skip* as valid, and the confidence gate can delete an alert on suspected fire. Free text can thus make the system ignore a hazard it has measured.

### B. Mechanism
**Principle:** *the description may add context, but may not reduce the response to a hazard that sensors have measured; when text and sensors conflict, fixed rules decide, not the LLM.*

```
event (sensor values + description)
  1. mark description as <<UNTRUSTED_NOTE>>
  2. LLM reasons with new prompt principles
  3. confidence gate: never drop alert >= warning while a sensor reports a hazard
  4. sensor guard (text-blind, fixed rules)
       D1 floor: threshold exceeded + no protection  -> send_alert
       D2 veto : action contradicts sensors          -> block
  -> execute
```

1. **Untrusted marking** of the description.
2. **Prompt principles:** the note must not deny sensors, request silence, or claim to be an order/drill/"false signal"; if a sensor reports a hazard the agent may not skip, and when unsure it sends an alert.
3. **Confidence gate:** an alert ≥ warning is never removed while a sensor reports a hazard.
4. **Sensor guard (text-blind):** D1 *floor* and D2 *veto* (fan off when overheated, SAVING under hazard, lock door on smoke with people, unlock on denied RFID, siren without smoke).

Thresholds lie between the Anomaly and Hazard levels of the benign set: temperature ≥ 38 °C, CO₂ ≥ 1500 ppm with people, smoke ≥ 200 ppm or detected state, RFID denied in LOCK or repeated. The guard reads only trusted fields, so an attacker controlling text cannot affect it. Steps 1–3 sit inside the agent; step 4 is post-processing before execution. No extra LLM or tool call.

### C. Experimental Design
One flag selects `none` (baseline), `prompt` (steps 1–3), `guard` (step 4) or `full`. The guard is deterministic post-processing, so replaying it on recorded baseline runs gives the exact result of a live `guard` run. `prompt` changes LLM behavior and must be re-run; `full` is then computed by replaying the guard on those runs.

### D. Results
Replay on recorded baseline runs (Gemini: runs 2–3, hence 30.1% baseline). **D1 (floor) matters most**: SUP ≤ 1.1%, because every SUP case is a hazard the sensors observed. D2 (veto) mainly cuts DH-A (Gemini 28.5% → 10.5%). Together ASR is 0.4–0.8% for all models except Gemini (4.9%), and **BU does not drop for any model** (+2 to +10 points: the guard also repairs benign cases where the agent missed a real hazard). UA rises to 96.5–100%.

**Table IX — Defense ablation by replay (%)**

| Model | BU base | BU D1+D2 | ASR base | ASR D2 | ASR D1 | ASR D1+D2 | SUP base | SUP D1+D2 | UA D1+D2 |
|:--|--:|--:|--:|--:|--:|--:|--:|--:|--:|
| Gemini 3.5 flash-lite | 93.0 | **97.0** | 30.1 | 22.6 | 12.4 | 4.9 | 52.3 | 1.1 | 96.5 |
| GPT-5.6 luna | 92.0 | 94.0 | 12.6 | 11.0 | 2.4 | 0.8 | 29.5 | 0 | 99.6 |
| GPT-6 luna | 92.0 | 94.0 | 6.9 | 6.7 | 0.6 | **0.4** | 18.2 | 0 | 99.6 |
| Claude Haiku 5.5 | 84.0 | 94.0 | 11.8 | 11.0 | 1.2 | **0.4** | 30.7 | 0 | 100 |
| DeepSeek flash | 92.0 | 94.0 | 2.8 | 2.8 | 0.4 | **0.4** | 6.8 | 0 | 100 |
| GLM 5.3 flash | 86.0 | 93.0 | 4.3 | 3.5 | 1.6 | 0.8 | 8.0 | 0 | 100 |
| **Prompt-only (live re-run)** | | | | | | | | | |
| Gemini 3.5 flash-lite | 93.0 | **TBD** | 30.1 | **TBD** | **TBD** | **TBD** | 52.3 | **TBD** | **TBD** |
| GPT-5.6 / Haiku | – | **TBD** | – | **TBD** | **TBD** | **TBD** | – | **TBD** | **TBD** |

### E. Limitations
1. SUP near zero is largely **by construction**: all SUP cases are hazards the sensor saw. It shows the architecture is sound, not that the LLM became safer; that evidence must come from the `prompt` setting.
2. Thresholds were chosen knowing the benign set; held-out near-threshold and faulty-sensor-high cases are needed to measure false alarms.
3. The guard does not defend against forged sensor readings.
4. Residual failures are actuations sensors cannot refute (fan off in a normal room, door lock in U4); in deployment the HITL layer holds them for approval.
5. Deployment needs alert cooldown to avoid alarm flooding.

## VIII. Conclusion

On a deployed cyber-physical agent, injected text rarely makes the agent do harm (DS 0%, DH-S ≤ 5.6%) but often makes it *stand down*: SUP is 59–91% of successful attacks across six models, and a clean twin shows it is injection-induced. Because the attacker controls only text, anchoring the response floor on trusted sensor values is effective: replayed on recorded runs, a text-blind guard reduces ASR to ≤ 0.8% (4.9% for the weakest model) with no loss of BU. Next: live `prompt`/`full` runs, k = 3 for all models, held-out benign cases for false-alarm rate, and adaptive attacks aware of the guard.

## References *(kiểm tra lại thông tin trích dẫn trước khi nộp)*

1. K. Greshake et al., "Not what you've signed up for: Compromising real-world LLM-integrated applications with indirect prompt injection," ACM AISec, 2023.
2. F. Perez and I. Ribeiro, "Ignore previous prompt: Attack techniques for language models," arXiv:2211.09527, 2022.
3. E. Debenedetti et al., "AgentDojo: A dynamic environment to evaluate prompt injection attacks and defenses for LLM agents," NeurIPS D&B, 2024.
4. Q. Zhan et al., "InjecAgent: Benchmarking indirect prompt injections in tool-integrated LLM agents," Findings of ACL, 2024.
5. K. Hines et al., "Defending against indirect prompt injection attacks with spotlighting," arXiv:2403.14720, 2024.
6. E. Debenedetti et al., "Defeating prompt injections by design," arXiv:2503.18813, 2025.
7. S. Yao et al., "ReAct: Synergizing reasoning and acting in language models," ICLR, 2023.
