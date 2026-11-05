# Sifely Smart Lock for Home Assistant

Monitor and (with a gateway) control Sifely smart locks from Home Assistant using the official Sifely Open API.

Version 2 replaces the legacy client ID and password login, which Sifely closed to new accounts. It authenticates with a single API key.

## Features

**Available without a gateway**

- Battery level for each lock
- Activity log with user name and success or failure for each event
- Passcode count, names, and validity dates (codes are never stored or shown)
- Read-only lock settings: auto-lock time, sound volume, passage mode, firmware version
- `sifely_activity` event for each new lock event, for use in automations

**Requires a Sifely gateway**

- Lock and unlock commands
- Lock state (locked or unlocked)

Without a gateway, the lock entity shows an unknown state. Lock and unlock attempts return a clear error.

## Requirements

- Home Assistant 2024.1 or later
- A Sifely account with an active Developer plan or higher at [connect.sifely.com](https://connect.sifely.com)
- An API key from the Account & API Key page on that site
- Optional: a Sifely Wi-Fi gateway (2.4 GHz) for remote control

## Installation

1. In HACS, open the menu, choose **Custom repositories**, and add `https://github.com/vmadhipa2018/sifely-ha-v2` as an Integration.
2. Download **Sifely Smart Lock** from HACS and restart Home Assistant.
3. Go to **Settings → Devices & services → Add integration** and select **Sifely Smart Lock**.
4. Paste your API key and submit.

If you used version 1, remove the old entry first. Its stored credentials don't work with version 2. Home Assistant will also prompt you to re-enter a key.

## Getting an API key

1. Sign in at [connect.sifely.com](https://connect.sifely.com).
2. Subscribe to a plan. The Developer plan is free for personal, non-commercial use.
3. Open **Account & API Key** and copy the key. It starts with `sk-`.

The key is not your Sifely app password.

## Events

Each new activity record triggers a `sifely_activity` event:

| Field | Description |
|---|---|
| `lock_id` | Numeric lock ID |
| `lock_alias` | Lock name in the Sifely app |
| `record_id` | Unique record ID |
| `record_type` | Event type code from the lock (not yet mapped to labels) |
| `success` | `true` if the operation succeeded |
| `username` | User name, if available |
| `lock_date` | Event time in milliseconds since the epoch |

Example automation trigger:

```yaml
trigger:
  - platform: event
    event_type: sifely_activity
    event_data:
      success: false
```

## Polling and API usage

Updates run on separate schedules to stay within the Developer plan's 10,000-call monthly limit:

| Data | Interval |
|---|---|
| Lock list and battery | 1 hour |
| Lock detail and settings | 2 hours |
| Activity records | 2 hours |
| Passcode list | 6 hours |
| Lock state (gateway only) | 30 minutes |

For three locks, this is about 3,240 calls per month. Failed calls also count toward the quota.

## Security

- The API key is stored in Home Assistant's config entry storage. Anyone with access to your Home Assistant files can read it.
- Anyone with the key can read lock data and, with a gateway, operate the locks. Protect it as you would a password.
- If the key is exposed, regenerate it at [connect.sifely.com](https://connect.sifely.com). The old key stops working immediately.
- Keypad codes, lock encryption keys, and admin passwords are never stored or exposed.

## Limitations

- **Polling only.** Sifely's webhooks are not yet active, so changes made in the Sifely app appear on the next poll.
- **Read-only settings.** Auto-lock time, sound volume, and passage mode can be viewed but not changed. The Open API does not document endpoints for changing them.
- **New locks need a reload.** Locks added to your account after setup appear after you reload the integration.
- **Event codes are raw.** Record type numbers are passed through without labels until they are mapped.

## Troubleshooting

| Message | Likely cause |
|---|---|
| "The API key was rejected" | The key was copied incorrectly, or it was regenerated |
| "Your Sifely subscription is not active" | The plan has lapsed. Check connect.sifely.com |
| "Your Sifely API quota is used up" | The monthly call limit was reached. It resets at the end of the billing cycle |
| "not connected to a Sifely gateway" | Remote control needs a gateway. Battery and activity still work |

Enable debug logging for `custom_components.sifely` to see details.

## Disclaimer

This is an unofficial community integration. It is not affiliated with or supported by Sifely. Use it at your own risk, especially for controlling door locks.

## License

See [LICENSE](LICENSE).
