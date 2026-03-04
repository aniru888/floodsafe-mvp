# WhatsApp Integration — Comprehensive Test Suite Design

> Date: 2026-03-04
> Status: Approved
> Scope: Rigorous testing of all WhatsApp features across both transports

---

## Goal

Build a comprehensive pytest test suite that verifies every WhatsApp feature path, covering both the Twilio and Meta Cloud API transports. Includes unit tests, integration tests, edge case coverage, and live endpoint smoke tests.

## Current State

### Existing Tests (2 files, ~20 tests)
- `test_webhook.py` — Rate limiting (4), input validation (4), signature validation (2), webhook endpoint (2)
- `test_report_creation.py` — Report creation with ML metadata (8)

### Coverage Gaps
- **Zero tests** for: Meta webhook, command handlers, session state machine, button handling, account linking, Wit.ai NLU, Llama AI summaries, Meta Graph API client, transport parity, bilingual templates, security edge cases, live endpoints

## Architecture

### WhatsApp System Under Test

```
Inbound: User → WhatsApp → Twilio/Meta → Webhook → Session → Route → Handler → Response
Outbound: Alert/Circle → Notification Service → Meta Graph API / Twilio SMS → User
```

**Two parallel transports, shared services:**
- `POST /api/whatsapp` — Twilio (form-encoded, TwiML response)
- `POST /api/whatsapp-meta` — Meta Cloud API (JSON, Graph API outbound, HMAC-SHA256)

**Shared layer:**
- `whatsapp/command_handlers.py` — RISK, WARNINGS, MY AREAS, HELP, STATUS
- `whatsapp/message_templates.py` — Bilingual EN/HI templates
- `whatsapp/photo_handler.py` — TFLite flood classification
- `whatsapp/button_sender.py` — Twilio Quick Reply buttons
- `whatsapp/meta_client.py` — Meta Graph API client
- `wit_service.py` — Wit.ai NLU intent classification
- `llama_service.py` — AI risk summaries (Groq/Meta Llama)

### Test File Structure

```
tests/test_whatsapp/
├── conftest.py               # Shared fixtures (EXPAND existing)
├── test_webhook.py           # Twilio webhook tests (EXPAND existing)
├── test_report_creation.py   # Report creation (KEEP existing)
├── test_meta_webhook.py      # NEW: Meta Cloud API webhook (~18 tests)
├── test_command_handlers.py  # NEW: Command handlers (~15 tests)
├── test_session_states.py    # NEW: Session state machine (~14 tests)
├── test_message_templates.py # NEW: Template rendering (~6 tests)
├── test_photo_handler.py     # NEW: ML classification (~11 tests)
├── test_button_handling.py   # NEW: Quick Reply button routing (~8 tests)
├── test_account_linking.py   # NEW: LINK flow (~11 tests)
├── test_meta_client.py       # NEW: Graph API client (~12 tests)
├── test_transport_parity.py  # NEW: Cross-transport verification (~5 tests)
├── test_security_edge_cases.py # NEW: Security edge cases (~6 tests)
├── test_bilingual.py         # NEW: Bilingual edge cases (~4 tests)
└── test_live_endpoints.py    # NEW: Live smoke tests (~5 tests)
```

**Total: ~111 test functions** across 12 new files + 2 existing.

---

## Test Cases Per File

### `test_meta_webhook.py` (~18 tests)

**Core functionality:**
| Test | Verifies |
|------|----------|
| `test_verify_webhook_valid_token` | GET with correct hub.verify_token returns hub.challenge |
| `test_verify_webhook_invalid_token` | GET with wrong token → 403 |
| `test_invalid_signature_rejected` | POST without valid HMAC-SHA256 → 403 |
| `test_disabled_returns_status_disabled` | POST when META_WHATSAPP_TOKEN not set → `{"status":"disabled"}` |
| `test_non_whatsapp_object_ignored` | POST with `object: "page"` → 200 OK silently |
| `test_text_message_processed` | POST with text → welcome response via Graph API |
| `test_location_message_creates_session` | POST with location → session enters `awaiting_photo` |
| `test_image_with_pending_location` | Image after location → report created, session reset |
| `test_button_reply_routed` | Interactive button_reply → correct handler called |
| `test_rate_limit_enforced` | 11th message in 60s → rate limit message |
| `test_mark_as_read_called` | Every message → `mark_as_read()` called |
| `test_health_endpoint` | GET health → status with meta/ml/wit info |

**Edge cases:**
| Test | Verifies |
|------|----------|
| `test_malformed_json_returns_ok` | Invalid JSON → 200 OK (don't error) |
| `test_missing_from_field_ignored` | No `from` field → silently skipped |
| `test_empty_text_body` | Empty text → welcome response |
| `test_very_long_text_handled` | 10KB text → doesn't crash |
| `test_unknown_message_type` | Type `"audio"` → welcome message |
| `test_duplicate_message_id` | Same message_id twice → no duplicate reports |

### `test_command_handlers.py` (~15 tests)

**Core functionality:**
| Test | Verifies |
|------|----------|
| `test_risk_with_place_name` | Geocodes → risk-at-point → formatted response |
| `test_risk_with_last_location` | Skips geocode → correct response |
| `test_risk_no_location` | → RISK_NO_LOCATION template |
| `test_risk_geocode_failure` | Place not found → LOCATION_NOT_FOUND |
| `test_risk_api_failure_fallback` | Risk API 500 → graceful LOW risk |
| `test_risk_with_llama_summary` | Llama enabled → AI summary appended |
| `test_warnings_active_alerts` | Alerts exist → WARNINGS_ACTIVE |
| `test_warnings_no_alerts` | → WARNINGS_NONE |
| `test_my_areas_linked` | Watch areas → MY_AREAS list |
| `test_my_areas_unlinked` | → ACCOUNT_NOT_LINKED |

**Edge cases:**
| Test | Verifies |
|------|----------|
| `test_risk_geocode_timeout` | httpx timeout → fallback message |
| `test_risk_api_returns_empty_json` | `{}` → LOW risk default |
| `test_risk_fhi_boundary_values` | FHI 0.3 → moderate, 0.6 → high |
| `test_warnings_malformed_alerts` | Missing fields → no crash |
| `test_my_areas_zero_watch_areas` | User, no areas → MY_AREAS_EMPTY |

### `test_session_states.py` (~14 tests)

**Core state transitions:**
| Test | Verifies |
|------|----------|
| `test_new_session_starts_idle` | First message → `idle` |
| `test_location_to_awaiting_photo` | Location → `awaiting_photo` |
| `test_photo_after_location_to_idle` | Photo → report → `idle` |
| `test_skip_during_awaiting_photo` | SKIP → report without photo → `idle` |
| `test_expired_session_resets` | >30 min → reset to `idle` |
| `test_link_to_awaiting_choice` | LINK → `awaiting_choice` |
| `test_choice_1_to_awaiting_email` | "1" → `awaiting_email` |
| `test_email_to_idle` | Valid email → `idle` |

**Edge cases:**
| Test | Verifies |
|------|----------|
| `test_corrupted_session_data_recovery` | `data=None` → graceful reset |
| `test_photo_without_pending_lat` | Missing `pending_lat` → no crash |
| `test_rapid_fire_messages` | 5 msgs <1s → rate limiter, no deadlock |
| `test_random_text_in_awaiting_photo` | → reminder, not crash |
| `test_cancel_during_awaiting_email` | CANCEL → idle, no user |
| `test_session_survives_db_rollback` | DB error → session usable next msg |

### `test_message_templates.py` (~6 tests)

| Test | Verifies |
|------|----------|
| `test_all_templates_both_languages` | Every key has `en` + `hi` |
| `test_template_substitution` | Variables injected correctly |
| `test_missing_variable_graceful` | Missing kwarg → template with `{placeholder}` |
| `test_format_risk_factors` | Elevation, rainfall, drainage, hotspot combos |
| `test_format_alerts_list` | Severity emojis (RED→🔴, ORANGE→🟠, YELLOW→🟡) |
| `test_format_watch_areas` | Labels, risk levels, counts formatted |

### `test_photo_handler.py` (~11 tests)

**Core:**
| Test | Verifies |
|------|----------|
| `test_classify_flood_detected` | High confidence → `is_flood=True` |
| `test_classify_no_flood` | Low → `is_flood=False, needs_review=True` |
| `test_classify_ml_disabled` | `ML_ENABLED=False` → None |
| `test_download_twilio_success` | Correct auth → bytes |
| `test_download_twilio_failure` | 404 → None |
| `test_severity_mapping` | Confidence → correct severity text |

**Edge cases:**
| Test | Verifies |
|------|----------|
| `test_classify_empty_bytes` | `b""` → None |
| `test_classify_non_image` | PDF bytes → graceful handling |
| `test_download_non_image_content_type` | `application/pdf` → None |
| `test_severity_at_boundaries` | 0.4/0.6/0.8 → correct band |
| `test_process_sos_download_fails` | Download fails → `(None, None)` |

### `test_button_handling.py` (~8 tests)

| Test | Verifies |
|------|----------|
| `test_report_flood_button` | → instructions |
| `test_check_risk_with_location` | → risk check |
| `test_check_risk_no_location` | → prompt |
| `test_view_alerts_button` | → warnings |
| `test_add_photo_with_pending` | → `awaiting_photo` |
| `test_submit_anyway_button` | → report without photo |
| `test_cancel_resets_keeps_location` | → idle, last_lat preserved |
| `test_unknown_button_shows_menu` | → menu |

### `test_account_linking.py` (~11 tests)

**Core:**
| Test | Verifies |
|------|----------|
| `test_link_already_linked` | → "already linked" |
| `test_choice_create_account` | → `awaiting_email` |
| `test_choice_stay_anonymous` | → idle |
| `test_email_existing_user_links` | → phone updated, session linked |
| `test_email_new_user_created` | → User(auth_provider="whatsapp") |
| `test_email_different_phone_rejected` | → error |
| `test_pending_report_linked` | → report.user_id updated |

**Edge cases:**
| Test | Verifies |
|------|----------|
| `test_invalid_email_rejected` | "not-an-email" → re-prompt |
| `test_email_at_only_rejected` | "@" → re-prompt |
| `test_cancel_during_email` | "cancel" → idle |
| `test_pending_report_linked_after_creation` | Anonymous report → linked |

### `test_meta_client.py` (~12 tests)

**Core:**
| Test | Verifies |
|------|----------|
| `test_send_text_success` | 200 → True |
| `test_send_text_4xx_no_retry` | 400 → False, 1 attempt |
| `test_send_text_5xx_retries` | 500 → 3 attempts with backoff |
| `test_send_interactive_buttons` | Correct payload shape |
| `test_download_media_two_step` | URL fetch → content → bytes |
| `test_download_media_timeout_retries` | Timeout → retries |
| `test_mark_as_read` | Correct payload |
| `test_send_text_sync` | Synchronous variant works |

**Edge cases:**
| Test | Verifies |
|------|----------|
| `test_button_title_truncated` | >20 chars → truncated |
| `test_max_3_buttons_enforced` | 5 buttons → only 3 sent |
| `test_phone_plus_stripped` | `"+91..."` → `"91..."` |
| `test_unknown_exception_no_retry` | ConnectionError → False, no retry |

### `test_transport_parity.py` (~5 tests)

| Test | Verifies |
|------|----------|
| `test_both_handle_text_commands` | RISK/WARNINGS/HELP on both |
| `test_both_handle_location` | Location → `awaiting_photo` |
| `test_both_handle_button_ids` | Same 9 button IDs |
| `test_both_handle_account_linking` | LINK flow on both |
| `test_both_handle_session_timeout` | 30-min timeout identical |

### `test_security_edge_cases.py` (~6 tests)

| Test | Verifies |
|------|----------|
| `test_hmac_wrong_secret` | Wrong app secret → 403 |
| `test_hmac_missing_header` | No header → 403 |
| `test_hmac_malformed_prefix` | `"md5=abc"` → 403 |
| `test_twilio_dev_mode` | No auth token → validation skipped |
| `test_phone_injection_sanitized` | SQL in phone → no injection |
| `test_xss_in_body_escaped` | `<script>` → stored as text |

### `test_bilingual.py` (~4 tests)

| Test | Verifies |
|------|----------|
| `test_hindi_risk_response` | Hindi user → Hindi template |
| `test_hinglish_wit_classification` | "kya flood hai?" → risk intent |
| `test_unknown_language_defaults_en` | "fr" → English |
| `test_hindi_button_labels` | All sets have Hindi equivalents |

### `test_live_endpoints.py` (~5 tests)

All tests marked `@pytest.mark.live` (skipped unless `--run-live` flag).

| Test | Verifies |
|------|----------|
| `test_twilio_health` | GET `/api/whatsapp/health` → 200 |
| `test_meta_health` | GET `/api/whatsapp-meta/health` → 200 |
| `test_meta_verify` | GET with hub params → challenge |
| `test_meta_unsigned_rejected` | POST without sig → 403 |
| `test_meta_text_message` | POST signed → 200 |

---

## Implementation Approach

### conftest.py Expansion

New shared fixtures needed:
- `meta_client` — TestClient for the FastAPI app
- `mock_meta_send_text` — Patches `meta_client.send_text_message` to capture outbound messages
- `mock_meta_send_buttons` — Patches `meta_client.send_interactive_buttons`
- `mock_meta_download_media` — Returns fake image bytes
- `mock_wit_ai` — Patches `wit_service.classify_message` with configurable responses
- `mock_llama` — Patches `llama_service.generate_risk_summary`
- `sample_meta_text_message` — Valid Meta webhook JSON payload
- `sample_meta_location_message` — Meta location message payload
- `sample_meta_image_message` — Meta image message payload
- `sample_meta_button_reply` — Meta interactive button reply
- `valid_hmac_signature` — Fixture that computes correct HMAC for test payloads
- `mock_risk_api` — Patches internal httpx calls to risk-at-point
- `mock_alerts_api` — Patches internal httpx calls to unified alerts
- `db_session_with_user` — DB fixture with a pre-created user
- `db_session_with_session` — DB fixture with an existing WhatsApp session

### Mocking Strategy

1. **DB**: Mock `get_db` dependency to return a mock Session with configurable query returns
2. **Meta Graph API**: Mock `httpx.AsyncClient` in `meta_client.py` to capture outbound calls
3. **ML classifier**: Mock `get_classifier()` to return configurable results
4. **Wit.ai**: Mock `classify_message()` to return `WitIntent` objects
5. **Llama**: Mock `generate_risk_summary()` to return test strings
6. **Internal APIs**: Mock httpx calls to `/api/hotspots/risk-at-point` and `/api/alerts/unified`

### Test Execution

```bash
# Run all WhatsApp tests
cd apps/backend && pytest tests/test_whatsapp/ -v

# Run only edge cases
cd apps/backend && pytest tests/test_whatsapp/ -v -k "edge"

# Run live tests (requires running server)
cd apps/backend && pytest tests/test_whatsapp/test_live_endpoints.py --run-live

# Run with coverage
cd apps/backend && pytest tests/test_whatsapp/ --cov=src/api/webhook --cov=src/api/whatsapp_meta --cov=src/domain/services/whatsapp --cov-report=term-missing
```

---

## Success Criteria

- All 111 tests pass
- Coverage >90% for all WhatsApp files
- Both transports proven to handle same features
- Edge cases documented and handled
- Live smoke tests verify production endpoints respond correctly
