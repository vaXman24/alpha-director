==============================================================================
Alpha Director — Formula Comparison Backtest (Track A)
==============================================================================
Snapshot days: 13 | total picks: 203
Window: 2026-04-21 -> 2026-05-04

### Forward window: +3d (vs SPY) — 128 of 203 picks have forward data
                 n  mean_excess  median_excess  hit_rate    best   worst  ci95_low  ci95_high
strategy                                                                                     
ActionCenter    40      -0.0062        -0.0003    0.4750  0.0794 -0.1056     0.329      0.625
DCA             30      -0.0123        -0.0081    0.3333  0.1185 -0.1032     0.192      0.512
HighConviction  18       0.0015         0.0040    0.5000  0.0395 -0.0605     0.290      0.710
UpsideOnly      40      -0.0048         0.0055    0.5500  0.1185 -0.1058     0.398      0.693

### Forward window: +5d (vs SPY) — 97 of 203 picks have forward data
                 n  mean_excess  median_excess  hit_rate    best   worst  ci95_low  ci95_high
strategy                                                                                     
ActionCenter    30      -0.0104        -0.0123    0.4333  0.0551 -0.0877     0.274      0.608
DCA             25      -0.0194        -0.0123    0.3200  0.0284 -0.1076     0.172      0.516
HighConviction  12      -0.0072        -0.0123    0.3333  0.0339 -0.0374     0.138      0.609
UpsideOnly      30      -0.0044         0.0132    0.5667  0.0728 -0.1045     0.392      0.726

### Forward window: +10d (vs SPY) — 0 of 203 picks have forward data
  (no completed forward windows yet)

### Pick overlap (any horizon)
strategy                  ActionCenter                          DCA HighConviction               UpsideOnly
snapshot_date                                                                                              
2026-04-21       AMZN,AVGO,QQQ,TSM,VOO  AMZN,CSPX.L,IWDA.AS,QQQ,VOO            NaN    AMZN,AVGO,QQQ,TSM,VOO
2026-04-23      AAPL,APP,ARM,IONQ,NVDA      AMZN,AVGO,META,MSFT,TSM            NaN   APP,IONQ,META,MSFT,TSM
2026-04-24     BAC,CLSK,MATX,NVDA,SBLK       APP,AVGO,META,MSFT,TSM  BAC,MATX,SBLK  APP,CLSK,IONQ,MSFT,NVDA
2026-04-25     BAC,CLSK,MATX,NVDA,SBLK       APP,AVGO,META,MSFT,TSM  BAC,MATX,SBLK  APP,CLSK,IONQ,MSFT,NVDA
2026-04-26        ASML,BAC,C,CLSK,NVDA       APP,AVGO,META,MSFT,TSM     ASML,BAC,C  APP,CLSK,IONQ,MSFT,NVDA
2026-04-27        ASML,C,CLSK,KDP,NVDA                          NaN   ASML,BAC,KDP  APP,CLSK,IONQ,META,MSFT
2026-04-28         AMAT,C,JPM,KDP,NVDA                          NaN   AMAT,BAC,KDP  APP,CLSK,IONQ,META,MSFT
2026-04-29         AMAT,C,JPM,KDP,NVDA       APP,BAC,CLSK,MSFT,NVDA   BAC,KDP,NVDA  APP,CLSK,IONQ,MSFT,NVDA
2026-04-30        BAC,EA,FCX,MSFT,NVDA       APP,BAC,CLSK,MSFT,NVDA            NaN     ASML,BAC,C,MSFT,NVDA
2026-05-01         BAC,EA,FCX,IBB,MSFT       APP,BAC,CLSK,MSFT,NVDA            NaN     ASML,BAC,C,MSFT,NVDA
2026-05-02         BAC,EA,FCX,IBB,MSFT       APP,BAC,CLSK,MSFT,NVDA            NaN     ASML,BAC,C,MSFT,NVDA
2026-05-03         BAC,EA,FCX,IBB,MSFT       APP,BAC,CLSK,MSFT,NVDA            NaN     ASML,BAC,C,MSFT,NVDA
2026-05-04       ASML,COPX,EA,FCX,MSFT       APP,BAC,CLSK,MSFT,NVDA            NaN  ASML,BAC,CLSK,MSFT,NVDA
