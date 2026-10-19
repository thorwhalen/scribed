# scribed.catalog

### scribed.catalog *= <Catalog 33 backends | 10 implemented | 17 local, 17 remote>*

`ocracy.kit.ledger.Catalog` bound to scribed’s data.

Loaded lazily from `DEFAULT_LEDGER_PATH` (override via the `path`
argument or the `SCRIBED_LEDGER` environment variable). `filter()`
returns a *new* `Catalog` over the matching subset, so filters compose:

```default
catalog.filter(is_remote=True).filter(pricing_model="free_tier_then_paid")
```

* **Type:**
  scribed’s ledger
