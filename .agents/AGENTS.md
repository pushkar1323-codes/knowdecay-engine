# KnowDecay Engine — Project Rules

## Intelligence Backbone (PERMANENT)

ALL intelligence systems MUST follow this pipeline:

```
MemoryState → Adaptive Stability → Decay Engine → Retention Estimate → Priority Engine → Scheduling Engine → Analytics
```

### Stage Definitions

| Stage | Engine | Purpose |
|-------|--------|---------|
| 1. MemoryState | `app/models/memory_state.py` | Single source of truth — load from DB or in-memory dict |
| 2. Adaptive Stability | `app/engine/stability_engine.py` | Compute S_adaptive BEFORE decay/retention |
| 3. Decay Engine | `app/engine/decay_engine.py` | Compute forgetting progression using S_adaptive |
| 4. Retention Estimate | `app/engine/retention_engine.py` / `recalibration_engine.py` | R = e^(-t/S_adaptive) |
| 5. Priority Engine | `app/engine/priority_engine.py` | Consumes pre-computed R — never estimates retention |
| 6. Scheduling Engine | `app/engine/scheduling_engine.py` | Uses R + S_adaptive + priority for interval computation |
| 7. Analytics | `app/engine/analytics_engine.py` | Downstream consumer of all prior stages |

### Rules

- **Stability BEFORE Decay**: S_adaptive must be computed before decay/retention estimation
- **No Skipping**: Every module that touches retention intelligence must pass through all stages
- **Separation of Concerns**: Priority never estimates retention. Scheduling never estimates priority
- **Pure Engine Layer**: All engine functions are stateless — no DB, no I/O, no side effects
- **MemoryState Persistence**: All 26+ CurrentState fields flow through MemoryState ORM — nothing is lost between events
- **Simulation Parity**: The simulation pipeline must mirror the service layer pipeline exactly
