# P8B path epoch summary

- `test_id`: `P8B-HDL-PATH-EPOCH-ATOMICITY`
- `status`: `PASS`
- `test_epoch_width`: `4`
- `accepted_commits`: `64`
- `expected_wraps`: `4`
- `stretched_request_exactly_once`: `True`
- `rejected_commit_no_increment`: `True`
- `atomic_all_lane_swap`: `True`
- `reset_during_commit_aborts`: `True`

```json
{
  "accepted_commits": 64,
  "atomic_all_lane_swap": true,
  "expected_wraps": 4,
  "rejected_commit_no_increment": true,
  "reset_during_commit_aborts": true,
  "stale_metadata_classes_rejected": [
    "readback",
    "frame",
    "ack",
    "object_or_path_status"
  ],
  "status": "PASS",
  "stretched_request_exactly_once": true,
  "test_epoch_width": 4,
  "test_id": "P8B-HDL-PATH-EPOCH-ATOMICITY"
}
```
