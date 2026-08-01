# P10.1 preflight receiver-prime timeout diagnosis

Diagnosis status: **PASS**  
Diagnosed hardware run: **FAIL**  
Run ID: `p10_1_hw_20260801T071828Z_bb6ce78a_1585d1ad_9ad4f85f`

The first nine preflight observations passed. Before `failed_object_diagnostic`, the rotating receiver did not accept/prime the next paired command within 38 seconds and remained at response sequence `0x3F2`, P10.1 state `0x7`, while PL/PHY were safe (`0x2` / `0x0`). The stage failed closed and did not execute any later campaign stage.

This is currently classified as a command-prime timeout, not an artifact defect. The new firmware branch only changes duplicate fault injection when the duplicate command flag is set on the DATA sender; preflight does not set that flag. A historical preflight completed all 11 observations, but that old-ELF PASS is used only as workflow comparison and is not inherited.

All shutdown paths passed for both boards. With the user's current complete-campaign authorization and unlimited retry override, the evidence-supported next step is a fresh unique run ID against the unchanged frozen artifacts. Source or artifact changes are not justified by this single timeout.
