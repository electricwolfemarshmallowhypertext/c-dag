(function () {
  "use strict";

  var METRICS_URL = "../validation/benchmark_metrics.json";
  var fallbackMetrics = {
    coverage: {
      public_financial_rows_processed_display: "100k+",
      validation_lanes: 6,
      file_corpus_inspected: 117,
      usable_structured_candidates: 102,
      public_data_domains_covered: [
        "mortgage performance",
        "mortgage applications",
        "consumer complaints",
        "CRT",
        "CAS",
        "public loss-exposure records"
      ]
    },
    validation_lanes_detail: [
      {
        lane: "Freddie + Fannie + HMDA",
        rows_processed: 30000,
        decision_distribution: { APPROVE: 9584, REVIEW: 4368, DECLINE: 16048 },
        replay_verification: "100% replay success on sampled validation audit records",
        audit_chain_verified: true
      },
      {
        lane: "CFPB complaints",
        rows_processed: 10000,
        decision_distribution: { APPROVE: 0, REVIEW: 9837, DECLINE: 163 },
        replay_verification: "100% replay success on sampled validation audit records",
        audit_chain_verified: true
      },
      {
        lane: "Freddie/STACR CRT",
        rows_processed: 10000,
        decision_distribution: { APPROVE: 9299, REVIEW: 0, DECLINE: 701 },
        replay_verification: "100% replay success on sampled validation audit records",
        audit_chain_verified: true
      },
      {
        lane: "Fannie CAS April 2026",
        rows_processed: 10000,
        decision_distribution: { APPROVE: 7948, REVIEW: 686, DECLINE: 1366 },
        replay_verification: "100% replay success on sampled validation audit records",
        audit_chain_verified: true
      },
      {
        lane: "Baseline outcome holdout",
        train_rows: 58579,
        test_rows: 41421,
        test_positives: 201,
        auc: 0.573062,
        pr_auc: 0.006059,
        decision_distribution: { APPROVE: 36336, REVIEW: 5085, DECLINE: 0 },
        replay_verification: "100% replay success on sampled validation audit records",
        audit_chain_verified: true
      }
    ],
    replay_verification: {
      statement: "Replay verification: 100% success on sampled validation audit records across reported validation runs."
    },
    audit_chain_integrity: {
      "validation_reports_status": "Audit-chain integrity: verified across reported validation runs; tamper behavior covered by tests.",
      tamper_test_result: {
        valid_chain_passes: true,
        modified_record_fails: true
      }
    },
    loss_exposure_mapping: {
      records_parsed: 5,
      record_sources_present: ["CFPB", "FINRA", "SEC", "OCC", "AI operational-loss research"],
      record_sources_not_yet_parsed: ["FFIEC"],
      cases: [
        {
          case_title: "CFPB / Wells Fargo $3.7B order",
          public_exposure_amount: "$3.7B",
          failure_type: "Consumer-harm and servicing-control breakdown.",
          missing_evidence_artifact: "Cross-workflow, replayable decision trace.",
          cdag_artifact_fit: ["trace", "counterfactual", "replay", "hash-chain", "evidence pack", "risk-exposure mapping"]
        },
        {
          case_title: "FINRA 2025 recurring fine categories",
          public_exposure_amount: null,
          failure_type: "Control, supervision, and record-integrity gaps.",
          missing_evidence_artifact: "Tamper-evident control evidence.",
          cdag_artifact_fit: ["replay", "hash-chain", "evidence pack", "risk-exposure mapping"]
        },
        {
          case_title: "SEC AI-washing enforcement focus",
          public_exposure_amount: null,
          failure_type: "Governance and disclosure mismatch.",
          missing_evidence_artifact: "Trace-backed governance documentation.",
          cdag_artifact_fit: ["trace", "counterfactual", "replay", "evidence pack", "risk-exposure mapping"]
        },
        {
          case_title: "AI operational-loss research in U.S. BHCs",
          public_exposure_amount: null,
          failure_type: "Operational-risk exposure growth.",
          missing_evidence_artifact: "Pre-escalation decision evidence.",
          cdag_artifact_fit: ["trace", "replay", "hash-chain", "risk-exposure mapping"]
        },
        {
          case_title: "OCC Spring 2025 risk framing",
          public_exposure_amount: null,
          failure_type: "Model, cybersecurity, and compliance-control gaps.",
          missing_evidence_artifact: "Integrated decision-level audit trail.",
          cdag_artifact_fit: ["trace", "replay", "hash-chain", "evidence pack", "risk-exposure mapping"]
        }
      ]
    },
    holdout_baseline: {
      train_rows: 58579,
      test_rows: 41421,
      test_positives: 201,
      auc: 0.573062,
      pr_auc: 0.006059,
      decision_distribution: { APPROVE: 36336, REVIEW: 5085, DECLINE: 0 }
    }
  };

  function formatNumber(value) {
    if (value === null || value === undefined) {
      return "";
    }
    if (typeof value === "number") {
      return value.toLocaleString("en-US");
    }
    return String(value);
  }

  function distributionText(distribution) {
    return "APPROVE " + formatNumber(distribution.APPROVE) +
      " / REVIEW " + formatNumber(distribution.REVIEW) +
      " / DECLINE " + formatNumber(distribution.DECLINE);
  }

  function setText(selector, text) {
    var node = document.querySelector(selector);
    if (node) {
      node.textContent = text;
    }
  }

  function renderCoverage(metrics) {
    var coverage = metrics.coverage;
    setText("[data-metric='rows']", coverage.public_financial_rows_processed_display);
    setText("[data-metric='lanes']", formatNumber(coverage.validation_lanes));
    setText("[data-metric='files']", formatNumber(coverage.file_corpus_inspected));
    setText("[data-metric='usable']", formatNumber(coverage.usable_structured_candidates));

    var list = document.querySelector("[data-domains]");
    if (!list) {
      return;
    }
    list.innerHTML = "";
    coverage.public_data_domains_covered.forEach(function (domain) {
      var item = document.createElement("li");
      item.textContent = domain;
      list.appendChild(item);
    });
  }

  function renderValidation(metrics) {
    var body = document.querySelector("[data-validation-body]");
    if (!body) {
      return;
    }
    body.innerHTML = "";
    metrics.validation_lanes_detail.forEach(function (lane) {
      var row = document.createElement("tr");
      var rows = lane.rows_processed
        ? formatNumber(lane.rows_processed)
        : "train " + formatNumber(lane.train_rows) + " / test " + formatNumber(lane.test_rows);
      var result = lane.auc
        ? "AUC " + lane.auc.toFixed(6) + " / PR-AUC " + lane.pr_auc.toFixed(6)
        : distributionText(lane.decision_distribution);

      row.innerHTML =
        "<td><strong>" + lane.lane + "</strong></td>" +
        "<td>" + rows + "</td>" +
        "<td>" + result + "</td>" +
        "<td>" + lane.replay_verification + "</td>" +
        "<td><span class='benchmark-status-ok'>" + (lane.audit_chain_verified ? "verified" : "not verified") + "</span></td>";
      body.appendChild(row);
    });
  }

  function renderLoss(metrics) {
    var grid = document.querySelector("[data-loss-cases]");
    if (!grid) {
      return;
    }
    grid.innerHTML = "";
    metrics.loss_exposure_mapping.cases.forEach(function (item) {
      var article = document.createElement("article");
      article.className = "benchmark-card";
      var exposureRow = item.public_exposure_amount
        ? "<p><strong>Exposure:</strong> " + item.public_exposure_amount + "</p>"
        : "";
      article.innerHTML =
        "<h3>" + item.case_title + "</h3>" +
        exposureRow +
        "<p><strong>Failure type:</strong> " + item.failure_type + "</p>" +
        "<p><strong>Missing artifact:</strong> " + item.missing_evidence_artifact + "</p>" +
        "<p><strong>C-DAG fit:</strong> " + item.cdag_artifact_fit.join(", ") + "</p>";
      grid.appendChild(article);
    });
  }

  function renderMetrics(metrics) {
    renderCoverage(metrics);
    renderValidation(metrics);
    renderLoss(metrics);

    setText("[data-replay-status]", metrics.replay_verification.statement);
    setText("[data-chain-status]", metrics.audit_chain_integrity.validation_reports_status);
    setText("[data-loss-records]", formatNumber(metrics.loss_exposure_mapping.records_parsed));
    setText("[data-loss-sources]", metrics.loss_exposure_mapping.record_sources_present.join(", "));
    setText("[data-loss-missing]", metrics.loss_exposure_mapping.record_sources_not_yet_parsed.join(", "));
    setText("[data-holdout-rows]", "train " + formatNumber(metrics.holdout_baseline.train_rows) + " / test " + formatNumber(metrics.holdout_baseline.test_rows));
    setText("[data-holdout-positives]", formatNumber(metrics.holdout_baseline.test_positives));
    setText("[data-holdout-metrics]", "AUC " + metrics.holdout_baseline.auc.toFixed(6) + " / PR-AUC " + metrics.holdout_baseline.pr_auc.toFixed(6));
    setText("[data-holdout-distribution]", distributionText(metrics.holdout_baseline.decision_distribution));
  }

  function loadMetrics() {
    if (!window.fetch) {
      renderMetrics(fallbackMetrics);
      return;
    }

    fetch(METRICS_URL)
      .then(function (response) {
        if (!response.ok) {
          throw new Error("Metrics request failed");
        }
        return response.json();
      })
      .then(renderMetrics)
      .catch(function () {
        renderMetrics(fallbackMetrics);
      });
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", loadMetrics);
  } else {
    loadMetrics();
  }
})();
