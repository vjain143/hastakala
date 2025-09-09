flowchart LR
  subgraph Clients
    U[Apps / BI Tools / JDBC]
  end

  U -->|Single JDBC/HTTP endpoint| GW[Trino Gateway]

  subgraph Blue[Cluster A]
    Acoord[Coordinator A]
    Awrk1[Workers A (6)]
  end

  subgraph Green[Cluster B]
    Bcoord[Coordinator B]
    Bwrk1[Workers B (6)]
  end

  GW <-->|Routes new sessions/queries| Acoord
  GW <-->|Routes new sessions/queries| Bcoord

  subgraph CI[CI/CD or Ops]
    PIPE[Drain/Roll/Activate Script]
  end

  PIPE -->|Deactivate/Activate via REST| GW
  PIPE -->|Rollout restart + health check| Acoord
  PIPE -->|Rollout restart + health check| Bcoord

  classDef gw fill:#fdf6e3,stroke:#b58900,stroke-width:1.5px;
  classDef coord fill:#e6f7ff,stroke:#1890ff,stroke-width:1.5px;
  classDef workers fill:#f0fff4,stroke:#2ecc71,stroke-width:1px;
  class GW gw;
  class Acoord,Bcoord coord;
  class Awrk1,Bwrk1 workers;