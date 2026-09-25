You are editing our LaTeX project report "Real-Time Hand Gesture Based Vehicle Control Using Static Gesture Recognition and Continuous Hand Tracking" (Phase 1, CHRIST University). The current text describes an OLD prototype (inference/dynamic_mediapipe_test.py, where only one control channel is active at a time, panicStop is always false and YOLO is not connected). The implementation has since been completed. The appendix figures already show the new system, so the text contradicts them. Rewrite the report so that it describes the CURRENT system below. Keep the old prototype only as the "first iteration" in the methodology.

GLOBAL RULES
- Keep all front matter (title page, vision/mission, POs/PSOs, certificates, acknowledgement) unchanged except where noted.
- Use the replacement text below. Where I say "replace", substitute the whole paragraph or section. Keep our heading numbering.
- Typeset every file name, identifier and code token with \path{...} (or \texttt{} with \usepackage[T1]{fontenc}) so underscores render properly, e.g. \path{mediapipe_thumb_controller.py}, \path{no_gesture}, \path{gesture_yolo11n_best.pt}. At the moment some names show faint or missing underscores.
- Delete every "confirmed in ..." / "confirmed by inspecting ..." / "confirmed by the absence of ..." phrase. They read like review notes.
- Delete the word "committed" wherever it refers to the controller ("the committed MediaPipe controller" becomes "the MediaPipe controller").
- Do not invent numbers. Use only the numbers given here.
- Cite the One Euro filter as a new reference: G. Casiez, N. Roussel, and D. Vogel, "1 € Filter: A Simple Speed-based Low-pass Filter for Noisy Input in Interactive Systems," in Proceedings of the SIGCHI Conference on Human Factors in Computing Systems (CHI), pp. 2527–2530, 2012, doi: 10.1145/2207676.2208639.
- Renumber the references in order of first citation (IEEE style). The Ultralytics licence reference is currently [3] but is first cited in Chapter 5.

==================================================================
FACT SHEET (the only source of truth for technical content)
==================================================================
Programs
- YOLO application (standalone demo): inference/live_gesture_control.py. It uses confidence 0.5, logs to logs/gesture_control_log.csv at most once per second, and applies the 9-label mapping in Table 4.1 (column 3).
- Integrated controller: simulator/mediapipe_thumb_controller.py. It runs MediaPipe AND YOLO11-nano in ONE program and streams UDP to the Pygame simulator (simulator/main.py). It starts the simulator itself ("closed loop"). Closing either window closes both. The flag --no-simulator runs the controller alone.
- Initial prototype (first iteration): inference/dynamic_mediapipe_test.py. Exponential moving average α = 0.15, 8-frame direction confirmation, left/right when |dx| > 0.45|dy|. Only ONE of steering/throttle/brake active at a time, and panicStop always false.

Dataset / training (unchanged, all verified)
- Hugging Face ntsrigaud/hagrid-subset, 9 classes, YOLO format, JPEG quality 92.
- Splits: 5,472 train / 645 validation / 1,079 test images (test held out).
- YOLO11-nano, 41 epochs, image size 640, batch 16 (fallback 8 on CUDA out-of-memory), 2 workers, NVIDIA RTX 4050 Laptop GPU.
- Test split: precision 0.989, recall 0.975, mAP@0.5 0.992, mAP@0.5:0.95 0.990, about 4.4 ms/image inference.
- Per class (P / R / mAP50): fist 1.000/0.983/0.995; palm 1.000/0.992/0.995; like 0.951/0.962/0.990; dislike 0.979/0.992/0.991; peace 0.997/1.000/0.995; ok 1.000/0.987/0.995; call 0.983/0.924/0.982; stop 1.000/0.987/0.995; no_gesture 0.992/0.950/0.992.

Continuous control (MediaPipe Hand Landmarker, Tasks API, VIDEO running mode with frame-to-frame tracking, 1 hand by default, detection/presence/tracking confidence 0.4)
- Steering = thumb ANGLE. Vector from thumb MCP (landmark 2) to thumb tip (landmark 4), converted to pixel coordinates (aspect-ratio corrected). Angle from vertical = atan2(dx, −dy): 0° = thumb up, negative = left, positive = right. The angle is taken relative to the user's calibrated neutral angle. A dead zone (default 8°) gives straight driving. Full lock is reached at a calibrated tilt (default 65°), with separate left and right ranges. An expo curve s = 0.65x + 0.35x³ gives finer control near centre. Hand size and distance from the camera do not affect it.
- Throttle/brake = PALM HEIGHT. Palm centre = mean of landmarks 0, 5, 9, 13, 17 (wrist and finger bases). Hand raised gives throttle, middle band gives coasting (default dead zone 0.16 of frame height around the centre 0.5), lowered gives brake. Default throttle/brake range 0.28 of frame height. Throttle and brake are mutually exclusive.
- Steering and pedals come from DIFFERENT features, so the driver can steer and accelerate/brake at the same time, and tilting the thumb does not change the throttle.
- Smoothing: One Euro filter per channel (adaptive low-pass: heavy smoothing when the hand is still, light smoothing when it moves fast). Parameters (min_cutoff, beta): steering (1.2, 0.8), throttle (0.8, 0.4), brake (1.5, 0.8).
- Hand loss: the last command is held for 0.25 s, then decays smoothly to idle (rate 3.0 per second) instead of snapping to zero.

Per-user calibration (calibration.py)
- A 5-step guided routine: NEUTRAL (thumb up, hand relaxed in the middle), FULL LEFT, FULL RIGHT, FULL THROTTLE (hand raised), FULL BRAKE (hand lowered).
- Each step has 1.5 s to get into position, then records for 2.5 s (about 20 s in total). The first 30% of each recording is discarded while the hand settles, and medians are used.
- Derived values:
  - neutral thumb angle;
  - separate left/right full-lock angles (85% of comfortable reach);
  - steering dead zone = 3 × standard deviation of the neutral angle, limited to 4–15°;
  - pedal centre;
  - pedal dead zone = 6 × standard deviation of palm height, limited to 0.08–0.20;
  - throttle and brake ranges (85% of reach).
- If a step sees fewer than 5 usable frames, it is repeated. If a range is too small (tilt < dead zone + 10°, or pedal span < 0.08), that axis keeps the default and a note is recorded.
- Profiles are saved per user as JSON. Calibration runs automatically for a new user, and the C key recalibrates.

Static commands through YOLO + MediaPipe fusion (gesture_commands.py)
- YOLO11-nano runs in a background thread on the newest camera frame (GPU when available, confidence 0.5, image size 640), so it never slows the MediaPipe driving loop.
- Commands in the integrated system: palm or stop → EMERGENCY STOP (while held); peace → toggle gear D ↔ R (one toggle per gesture); call → HORN (while held); like (thumbs-up) = the driving pose. The other classes (fist, dislike, ok, no_gesture) issue no command.
- Two-model agreement: a command is accepted only when YOLO's label (fresh ≤ 0.35 s old, confidence ≥ 0.55) AND MediaPipe's finger pattern agree. The finger pattern is computed rotation-invariantly: a finger is extended when its tip-to-wrist distance exceeds its PIP-to-wrist distance by more than 12%, and folded when the tip is closer to the wrist than the PIP joint. palm = 4 fingers extended; peace = only index and middle extended; call = only pinky extended; fist = all folded (the driving pose).
- Temporal voting: emergency stop needs 3 of the last 4 frames (about 100 ms at 30 fps). Gear and horn need 5 of the last 7 frames. The gear has a 1.0 s cooldown and re-arms only after the peace sign is released.
- Safety:
  - The emergency stop overrides everything and is fail-safe. If YOLO is unavailable or has no fresh result, MediaPipe's open-palm pattern alone triggers it.
  - While the driving hand forms a command shape, steering and pedals pause, so a gesture cannot jerk the wheel.
  - While the horn is held, the current steering and throttle are kept.
- Offline agreement test on the full held-out test split: the correct command fired on 107/120 palm (89.2%), 115/120 stop (95.8%), 104/120 peace (86.7%) and 94/119 call (79.0%) single images. On the 600 non-command images (like, fist, ok, dislike, no_gesture), 0 commands fired. In live use, voting over consecutive frames is applied on top of these per-image rates.
- Scripted scenario tests of the command logic: 17/17 passed (for example model disagreement, YOLO unavailable, a 3-frame flicker causing no gear change, horn followed by palm → stop wins).
- End-to-end replay test (real controller loop, recorded test images instead of the webcam, YOLO on the GPU): about 26–27 frames/s, gear toggled exactly once per peace sign, horn on after 5 frames and off within 2 frames of release, emergency stop after 3 frames and cleared 1 frame after the palm was lowered, no false commands in the driving pose.

UDP message (JSON, one per processed frame, port 5005)
{ "steeringAngle": -1.0..1.0, "throttle": 0.0..1.0, "brake": 0.0..1.0, "panicStop": true/false, "timestamp": send time, "gear": 1 (D) or -1 (R), "horn": true/false, "gesture": latest YOLO label (HUD only) }
- Numeric values are clamped and rounded to 4 decimals. The receiver accepts packets without the new fields (defaults: gear D, no horn), so older senders such as the mock sender still work.
- Aliased key names are accepted, malformed packets are counted and dropped, and after 0.5 s without a valid packet the simulator falls back to keyboard/idle.

Simulator changes
- Gear R: the throttle hand drives the car backwards. If the car is still rolling forward, reverse acts as a brake first, so shifting while moving slows the car and then reverses it, with no jolt.
- Horn: a two-tone (400 Hz + 500 Hz) looping sound plus a HUD badge. It stays silent if no audio device is present.
- HUD shows the gear selector (SELECT: D/R) and the received YOLO gesture label.
- Speed-sensitive steering: maximum wheel angle scales linearly from 20° at standstill to 40% of that at top speed, and the wheel turn rate from 120°/s to 60% of that. Measured yaw rate at full lock: 1.52 → 1.27 rad/s at 200 px/s, 3.79 → 2.35 rad/s at 500 px/s, 6.45 → 2.42 rad/s at 850 px/s.
- All 14 simulator unit tests pass.
- Tooling: every session writes a per-frame CSV log (logs/gesture_session_<date>_<time>.csv) with both models' outputs, votes and control values. The P key saves a matched camera + simulator screenshot pair.

Not measured (keep these honest limitations): live-webcam recognition accuracy, true camera-to-simulator latency, user studies.

==================================================================
SECTION-BY-SECTION CHANGES
==================================================================

FRONT MATTER
1. Page 8 ("Industry Certificate") is still the template placeholder ("Certificate PDF File has to kept in the Pictures Folder..."). If we have no industry certificate, remove the page and its Contents entry. Otherwise insert IndustryCertificate.pdf. Its Contents page number must be vii (it currently shows vi, the same as the Bonafide certificate), and the page must carry its roman numeral.
2. Declaration: replace "degree of Bachelor of Technology in AI and Data Science Engineering" with "degree of Bachelor of Technology in Computer Science and Engineering - Artificial Intelligence and Machine Learning" so it matches the title page and certificate.

ABSTRACT: replace the whole abstract with:
"Driving a vehicle still depends on physical controls such as a steering wheel, pedals and switches. This project builds a contactless, camera-based alternative: a person drives a simulated vehicle using hand gestures captured by an ordinary webcam, with potential applications in assistive human–machine interfaces.
The system fuses two complementary vision models in one real-time controller. MediaPipe Hand Landmarker tracking provides continuous control. The tilt angle of the thumb steers the vehicle, and the height of the palm sets the throttle or brake. Because the two come from different hand features, steering and acceleration can be applied at the same time. A One Euro adaptive filter suppresses jitter without adding lag, and a 20-second per-user calibration adapts the neutral pose, ranges and dead zones to each driver. A YOLO11-nano model, fine-tuned for 41 epochs on a nine-class HaGRID subset, recognises static command gestures: open palm for emergency stop, peace sign for gear change and call sign for horn. On the held-out test split of 1,079 images it achieved precision 0.989, recall 0.975, mAP@0.5 of 0.992 and mAP@0.5:0.95 of 0.990. A command is executed only when YOLO's label and MediaPipe's finger pattern agree over several frames. On the 600 non-command test images this produced no false commands, and the emergency stop remains available through MediaPipe alone if YOLO is unavailable.
Control values and commands are streamed over UDP to a Pygame simulator based on a kinematic bicycle model with speed-sensitive steering, reverse gear and horn. All 14 simulator unit tests and 17 command-logic scenario tests passed. Live-webcam accuracy and true end-to-end latency were not measured; the reported recognition metrics apply to the held-out dataset test split."
Keywords (one line, no break): Static Gesture Recognition, YOLO11-nano, MediaPipe Hand Tracking, Multi-Model Fusion, One Euro Filter, User Calibration, Pygame Vehicle Simulator, UDP Communication, Human–Computer Interaction

1.1 CONTEXT: replace the last paragraph of p.1 and the first paragraph of p.2 with:
"The system combines two complementary vision models in a single controller program (\path{simulator/mediapipe_thumb_controller.py}). Continuous hand tracking with the MediaPipe Hand Landmarker (Tasks API) converts the thumb's tilt angle into steering and the palm's height into throttle or braking. Static gesture recognition with a YOLO11-nano model fine-tuned on a HaGRID subset recognises discrete command poses (emergency stop, gear change and horn). These are accepted only when they agree with the finger pattern measured by MediaPipe. The controller streams the control values and commands over UDP, through the shared \path{GestureClient} helper, to a Pygame vehicle simulator. The simulator displays speed, gear, steering angle, control values, the received gesture, packet rate, packet age and connection status. A standalone YOLO application (\path{inference/live_gesture_control.py}) is retained for demonstrating and logging all nine gesture classes."

1.3 PROBLEM IDENTIFICATION: replace the 4th bullet with:
"• Combining the discrete commands and the continuous control values in one control stream, so that commands can be issued without disturbing steering, and preventing false commands while driving."

1.4 PROBLEM FORMULATION: replace both paragraphs with:
"This project combines computer vision with systems integration by connecting camera-based input to a real-time simulator over a network. Two complementary mechanisms are used together. MediaPipe continuous hand tracking provides proportional steering, throttle and brake values. YOLO11-nano static gesture recognition provides discrete commands (emergency stop, gear D/R and horn). The commands are fused with MediaPipe's finger pattern so that each model checks the other.
The controller and the Pygame simulator are separate programs connected through a UDP message format (steeringAngle, throttle, brake, panicStop, timestamp, gear, horn, gesture). The controller launches the simulator automatically, so both run as one closed-loop system while remaining independently testable."

2.4 IDENTIFICATION OF GAPS: replace with:
"The reviewed approaches mostly address either gesture classification or hand tracking on its own. Few works combine a trained static-gesture detector with landmark-based continuous control in one real-time loop, or use each model to validate the other before a safety-relevant command is executed. This project investigates that practical integration: continuous MediaPipe control, YOLO11-nano commands confirmed by MediaPipe finger patterns and temporal voting, per-user calibration, and a fail-safe emergency stop. It does not claim a new detection architecture, hand-tracking model, networking protocol or vehicle-dynamics model."

2.5 NEED FOR RESEARCH: replace with:
"A single model is not sufficient for gesture-based driving. Class labels alone cannot provide smooth steering, while landmark tracking alone is prone to misreading a hand shape as a command. The project is needed to show how the two can be combined so that proportional control and discrete commands coexist safely, and how the result can be adapted to different users through calibration."

2.6 PROBLEM STATEMENT: replace with:
"To develop a real-time, webcam-based vehicle-control system in which MediaPipe continuous hand tracking provides simultaneous proportional steering, throttle and braking, YOLO11-based static gesture recognition provides discrete commands (emergency stop, gear change and horn) validated against MediaPipe finger patterns, and all control data is transmitted over UDP to a Pygame vehicle simulator, with per-user calibration and fail-safe behaviour when the hand or a model is lost."

2.7 OBJECTIVES: replace the list with:
"• To prepare a nine-class HaGRID subset (5,472 train / 645 validation / 1,079 test images) for static gesture recognition.
• To fine-tune YOLO11-nano on the nine classes and evaluate it on the held-out validation and test splits.
• To develop MediaPipe-based continuous control that maps thumb angle to steering and palm height to throttle/brake, allowing simultaneous steering and speed control, with adaptive (One Euro) smoothing.
• To design a per-user calibration procedure that adapts neutral pose, ranges and dead zones to each driver.
• To fuse YOLO commands with MediaPipe finger patterns and temporal voting, so that commands are reliable and the emergency stop is fail-safe.
• To design a UDP message format carrying control values and commands, and a Pygame simulator that applies them (including reverse gear, horn and speed-sensitive steering) with a live dashboard, and to verify the system with automated and scenario tests."

2.8 LIMITATIONS: replace the list with:
"• YOLO11-nano accuracy and the YOLO–MediaPipe command agreement were measured on the held-out dataset test split only. Live-webcam performance under different lighting, backgrounds, cameras and hand positions was not measured.
• True camera-to-simulator latency was not measured. The displayed packet age reflects network delivery only.
• Tracking uses one hand by default. An optional two-hand mode (driving with the closer hand, commands from either hand) roughly doubles MediaPipe processing time.
• On single test images, the correct command fired for 79.0% (call) to 95.8% (stop) of images. Live reliability relies on voting over consecutive frames.
• YOLO runs in real time on a GPU. On a CPU-only machine commands respond more slowly, although the emergency stop still falls back to MediaPipe.
• The simulator uses a simplified kinematic bicycle model without tyre, suspension or road-surface dynamics.
• Only three command gestures (palm/stop, peace, call) are used in the integrated controller. The remaining classes are recognised but issue no command.
• No user study has been carried out."

CHAPTER 3 METHODOLOGY
- Item 1: change the last sentence to: "Steering, throttle and braking were assigned to continuous hand tracking because they need proportional values. Emergency stop, gear change and horn were assigned to static gesture recognition because they are discrete."
- Item 4: replace with: "4. Continuous hand-tracking development (two iterations): The first prototype (\path{inference/dynamic_mediapipe_test.py}) classified the thumb direction into left/right/up/down (exponential moving average α = 0.15, 8-frame confirmation, |dx| > 0.45|dy|) and drove only one channel at a time. Testing showed that steering could not be combined with throttle and that full steering required the thumb to reach the frame edge. The final controller therefore maps the thumb angle to steering and the palm height to throttle/brake, smooths each channel with a One Euro filter, and holds and then decays the last command when the hand is lost."
- Insert a new item after 4: "5. Per-user calibration: a five-step guided routine (neutral, full left, full right, full throttle, full brake; about 20 s) records each user's comfortable poses and derives their neutral angle, ranges and dead zones, saved as a JSON profile."
- Item 6 (Integration): replace with: "Integration: MediaPipe and YOLO11-nano were combined in one controller. YOLO runs in a background thread and its labels are accepted as commands only when MediaPipe's finger pattern agrees over several frames. The UDP format was extended with gear, horn and gesture fields, and the controller was made to launch and close the simulator automatically."
- Item 7 (Testing): add: "an offline YOLO–MediaPipe agreement test on the whole test split, 17 command-logic scenario tests, and an end-to-end replay of the real controller loop with recorded images".
- Renumber the items.

4.1 SYSTEM ARCHITECTURE: replace the paragraph with:
"The system consists of a controller (Part A) and a simulator (Part B). Part A captures webcam frames and runs two models: MediaPipe Hand Landmarker on every frame for continuous control, and YOLO11-nano in a background thread for static commands. A fusion stage accepts a command only when both models agree, then sends the control values and commands to Part B over UDP. Part B validates the packets, updates the vehicle model and renders the city and dashboard (Figure 4.1)."
Figure 4.1 must be redrawn: add a "Command fusion (YOLO label + MediaPipe finger pattern, temporal voting)" block that receives arrows from BOTH model boxes and feeds the UDP arrow, and add "Per-user calibration" feeding the MediaPipe mapping. Change the UDP label to "steering, throttle, brake, panicStop, gear, horn, gesture". Change "Physics + Road + Obstacles" to "Vehicle physics + road/off-road detection" (the simulator has no obstacles or collisions). Please produce this as a TikZ diagram.

4.2 METHODOLOGY FOR THE STUDY: replace with:
"The implementation consists of: (1) the integrated controller (\path{simulator/mediapipe_thumb_controller.py} with \path{gesture_commands.py} and \path{calibration.py}), which runs MediaPipe and YOLO11-nano, fuses their outputs and sends UDP packets to 127.0.0.1:5005; (2) the Pygame simulator (\path{simulator/main.py}), which receives the packets and renders the vehicle and dashboard; and (3) the standalone YOLO application (\path{inference/live_gesture_control.py}) for demonstrating and logging all nine classes. The controller starts the simulator automatically, and closing either window closes both. The option \path{--no-simulator} allows the simulator to run separately or on another machine."

4.3 EXPERIMENTAL WORK: replace the bullets with:
"• YOLO evaluation: held-out 1,079-image test split (results in Chapter 5).
• Model agreement: YOLO and MediaPipe were run on every test image to measure how often the correct command fired and whether any command fired on non-command poses.
• Command-logic scenarios: 17 scripted scenarios, including model disagreement, YOLO unavailable, short gesture flickers, and horn followed by emergency stop.
• End-to-end replay: the real controller loop was fed recorded test images at 30 frames/s while packets were captured by the simulator's receiver.
• Mock-sender scenarios: slalom, panic, circle and interactive (the interactive mode is Windows-only).
• Robustness: malformed packets, missing or aliased fields, value clamping, packets without the new fields, and the 0.5 s timeout.
• Automated tests: all 14 simulator unit tests passed."

4.4 ANALYTICAL WORK: replace the second paragraph with:
"For continuous control, the thumb angle and palm height are passed through per-channel One Euro filters [ref]. Each filter's cutoff frequency rises with the speed of the signal, so a still hand is smoothed heavily while fast movements pass through with little lag. For commands, a label is accepted only if YOLO's result is fresh (≤ 0.35 s) and confident (≥ 0.55) and matches MediaPipe's finger pattern. An emergency stop then needs 3 of the last 4 frames; gear and horn need 5 of the last 7."

4.5.1 STATIC GESTURE-TO-COMMAND MAPPING: keep Table 4.1 but add a 4th column "Integrated controller": Fist –, Palm EMERGENCY STOP, Like driving pose (MediaPipe control), Dislike –, Peace GEAR D↔R, OK –, Call HORN, Stop EMERGENCY STOP, No gesture –. Rename the existing command column to "Standalone YOLO app label" and delete "(not sent to simulator)". Replace the paragraph below the table with: "The standalone application displays and logs the labels in column 3. In the integrated controller only the gestures in column 4 are used. Palm and stop both trigger the emergency stop because both are open-hand poses."
Add a new subsection 4.5.2 "Command Fusion and Safety" containing the two-model agreement, finger-pattern rule, voting, gear one-shot/cooldown, driving pause, horn hold, fail-safe stop and the agreement-test numbers from the fact sheet.

4.5.2 → 4.5.3 CONTINUOUS MAPPING: replace the text with the steering, pedal, smoothing and hand-loss facts from the fact sheet, and add a subsection on per-user calibration. Replace Table 4.2 with:
| Hand feature | Control | Mapping |
| Thumb angle from vertical (landmarks 2→4) | Steering −1…+1 | relative to calibrated neutral; dead zone (default 8°); full lock at calibrated tilt (default 65°), separate left/right; expo curve |
| Palm centre height (landmarks 0,5,9,13,17) above centre band | Throttle 0…1 | beyond the dead zone (default 0.16), full at the calibrated range (default 0.28) |
| Palm centre height below centre band | Brake 0…1 | as above |
| Palm in centre band | Coasting | throttle = brake = 0 |
| No hand | Hold 0.25 s, then decay to idle | |
Delete "simultaneous steering and throttle or braking are not currently supported".

4.5.3 → 4.5.4 UDP FORMAT: replace the JSON block with the 8-field message from the fact sheet. Replace the paragraph after it with the packet notes from the fact sheet, and delete "Static accelerate and brake labels are not transmitted..." and "...currently sends this field as false".

4.5.4 → 4.5.5 VEHICLE MODEL: add rows to Table 4.3: "Steering lock at top speed: 40% of maximum (linear with speed)" and "Steering rate at top speed: 60% of maximum". Add the yaw-rate measurements. Replace "Reverse currently comes from the keyboard S key because the UDP schema has no reverse field" with the gear-R behaviour and horn from the fact sheet. Keep the sentence that off-road adds resistance and a speed cap rather than a reduced-grip model.

4.6 PROTOTYPE & TESTING: replace the first paragraph with: "The prototype is one controller program that launches the simulator. The camera window shows the thumb angle, palm marker, control bars, gear, horn, both models' current outputs and the command vote counts. The simulator dashboard shows speed, gear and selector, steering angle, throttle, brake, received gesture, packet rate, packet age and connection status, together with a minimap and panic-stop and off-road indicators. Every session writes a per-frame CSV log, and the P key saves matched camera and simulator screenshots."

4.7 ALGORITHMS: 4.7.1 = the standalone YOLO flow (keep, but delete "The current pipeline ends on the control side..."). Replace 4.7.2 with the integrated controller loop:
"1. Capture and mirror the webcam frame; pass a copy to the YOLO background thread.
2. Run MediaPipe Hand Landmarker (VIDEO mode); compute the thumb angle, palm height and finger pattern.
3. Fuse the newest fresh YOLO label with the finger pattern and update the votes; derive emergency stop, gear and horn.
4. If the driving hand forms a command shape, pause driving (hold, then decay); otherwise map the angle and height through the user's calibration profile to steering, throttle and brake.
5. Smooth each channel with its One Euro filter; the emergency stop overrides with throttle 0 and brake 1.
6. Send the UDP packet, draw the overlay, write the log row, and repeat."
In 4.7.3 add "apply gear (R: throttle drives reverse) and horn" after step 3.

4.8 CODES/STANDARDS: replace "A main-repository requirements.txt is provided for the controller-side Python dependencies." with "The simulator's dependencies are listed in \path{simulator/requirements.txt}; the controller additionally requires Ultralytics and PyTorch (versions below). If the controller is started from an environment without Ultralytics, it restarts itself in the project environment." Keep the version list.

5.1 RESULTS: after the YOLO paragraph add the agreement-test result (89.2 / 95.8 / 86.7 / 79.0%, 0 of 600 false commands), the 17/17 scenario tests, the end-to-end replay results, and the speed-sensitive steering yaw-rate table. Replace the packet-rate sentence with: "The packet rate equals the controller's processing rate (about 26–27 Hz with YOLO on the GPU in the replay test); the displayed packet age was a few hundredths of a second, which is not true end-to-end latency."

5.3 DISCUSSIONS: replace the 2nd and 3rd paragraphs with: "Using the two models together was more reliable than either alone. On test images, MediaPipe's finger pattern sometimes misread a thumbs-up as an open hand, but YOLO disagreed and no command fired. YOLO in turn cannot provide proportional steering. Requiring agreement, plus voting over frames, removed false commands on non-command poses, while keeping the safety-critical emergency stop available through MediaPipe alone. Separating steering (thumb angle) from speed (palm height) removed the main limitation of the first prototype, which could not steer and accelerate at once."

5.6 CONCLUSIONS: replace items 2, 3 and 6 with:
"2. Mapping thumb angle to steering and palm height to throttle/brake, with One Euro smoothing and per-user calibration, allows simultaneous, proportional control that adapts to each driver.
3. A single controller fuses YOLO11-nano commands with MediaPipe finger patterns and streams control values and commands over UDP to the Pygame simulator, which launches and closes together with the controller.
6. Fusing the two models produced no false commands on 600 non-command test images while keeping a fail-safe emergency stop."

5.7 FUTURE WORK: delete the old items 2, 3, 4 and 5 (now done). Keep live-webcam testing and latency measurement. Add: "a user study comparing calibrated and uncalibrated control (lap time, lane deviation, jitter) using the per-frame session logs"; "driver-attention monitoring with MediaPipe face landmarks that slows the vehicle when the driver looks away"; "CPU-only optimisation of the YOLO stage"; "testing on a physical robot or RC vehicle".

APPENDIX A: restructure it as below. Use \includegraphics with these file names, which we will upload. Captions must say what each figure proves.
A.1 YOLO11 Static Gesture Recognition
  - A1_1_yolo_predictions_per_gesture_class.jpg: "YOLO11-nano predictions on held-out test images, one per class, with confidence and the command used in the integrated system. Test images from HaGRID (CC BY-SA 4.0)."
  - A1_2_confusion_matrix_test_set.png: "Normalised confusion matrix on the 1,079-image test split."
  - A1_3_precision_recall_curve_test_set.png: "Precision–recall curves on the test split (mAP@0.5 = 0.992)."
  - A1_5_training_curves.png: "Training and validation loss, precision/recall and mAP over 41 epochs."
A.2 MediaPipe Continuous Hand Tracking
  - A2_1_mediapipe_21_landmarks_and_finger_states.jpg: "The 21 hand landmarks, the thumb vector used for steering (green) and the per-finger states that produce the hand pattern checked against YOLO."
  - Keep our current Figure A.1, with the new caption: "Live controller: a +24° thumb tilt gives steering 0.41 while the raised palm gives throttle 0.34, so steering and throttle are applied simultaneously (user profile 'Sam', calibrated)."
A.3 Vehicle Simulator
  - A3_2_driving_and_steering.png (this REPLACES our current Figure A.2, which shows the car off-road under a "normal operation" caption), A3_4_reverse_gear.png, A3_5_horn.png, A3_6_offroad_detection.png, with short captions.
A.4 End-to-End Gesture-to-Vehicle Integration
  - Matched camera + simulator pairs (we will add them) for driving, peace → gear R, call → horn, and palm → emergency stop.
A.5 UDP Communication and Simulator Test Scenarios
  - A5_1_udp_connected_30hz.png, A5_2_malformed_packets_rejected.png (9 malformed packets counted and ignored), A5_3_panic_stop_engaged.png (keep our current Figure A.3 here), A5_4_panic_stop_vehicle_halted.png, A5_5_udp_timeout_keyboard_fallback.png, A5_6_minimal_packet_backward_compatible.png, A5_7_simulator_unit_tests.png.
Update the List of Figures to match.

APPENDIX B: in B.2 add "YOLO and MediaPipe run together in one controller; YOLO uses the GPU through PyTorch CUDA". In B.3 replace "A controller-side requirements.txt and the simulator's own dependency file" with "The simulator's requirements.txt and the project virtual environment".

GLOSSARY: remove CNN, GUI and IP Address (they are never used in the text). Add: "One Euro Filter – an adaptive low-pass filter whose smoothing decreases as the input moves faster", "Calibration Profile – per-user neutral pose, ranges and dead zones saved as JSON", "Command Fusion – accepting a static command only when YOLO and MediaPipe agree over several frames", "Dead Zone – a small input range around neutral that produces no output". Sort both glossary tables alphabetically.

LAYOUT: allow Table 4.1 to float with [htbp] or split it so that page 13 is not left half empty.
