import { DatePipe } from "../time";
import { Component, inject } from "@angular/core";
import { DecimalPipe } from "@angular/common";
import { Store } from "../store";
import { ModelDiagnosticsComponent } from "../components/model-diagnostics.component";
import { DrawArchiveComponent } from "../components/draw-archive.component";

@Component({
  standalone: true,
  imports: [
    DatePipe,
    DecimalPipe,
    ModelDiagnosticsComponent,
    DrawArchiveComponent,
  ],
  template: `
    <div class="page-intro">
      <p class="eyebrow">TRANSPARENT UTVÄRDERING</p>
      <h2>Tidigare omgångar</h2>
      <p class="muted">
        Tidsordnad utvärdering på separata säsonger. Dessa resultat är inte
        liveprestanda eller uppmätt spelavkastning.
      </p>
    </div>
    <app-draw-archive />
    <details class="advanced-model" (toggle)="loadDetails($event)">
      <summary>Fördjupad modellinfo</summary>
      @if (store.status()?.metadata; as metadata) {
        @if (metadata.evaluation) {
          <app-model-diagnostics [metadata]="metadata" />
        } @else if (metadata.split) {
          <section class="panel history-panel">
            <div class="section-line">
              <h3>Modellen är tränad</h3>
              <span class="tag">TEMPORALT BACKTEST</span>
            </div>
            <p>
              Tränad {{ metadata.trained_at | date: "yyyy-MM-dd HH:mm" }} ·
              {{ metadata.training_matches | number }} träningsmatcher ·
              {{ metadata.features.length }} inputs
            </p>
            <p class="muted">
              Data till och med {{ metadata.data_through }}. Ligor:
              {{ metadata.leagues.join(", ") }}
            </p>
            <div class="period-grid">
              @for (split of splits; track split.key) {
                <div>
                  <span class="eyebrow">{{ split.label }}</span>
                  <p>
                    {{ metadata.split[split.key].from }} →
                    {{ metadata.split[split.key].to }}
                  </p>
                  <strong
                    >{{
                      metadata.split[split.key].matches | number
                    }}
                    matcher</strong
                  >
                </div>
              }
            </div>
            <div class="table-scroll">
              <table>
                <caption>
                  Sluttest:
                  {{
                    metadata.split.test.seasons.join(", ")
                  }}
                </caption>
                <thead>
                  <tr>
                    <th>Prognos</th>
                    <th>Log Loss ↓</th>
                    <th>Brier Score ↓</th>
                    <th>Accuracy ↑</th>
                  </tr>
                </thead>
                <tbody>
                  <tr>
                    <th>Bookmaker baseline</th>
                    <td>
                      {{ metadata.test.market.log_loss | number: "1.4-4" }}
                    </td>
                    <td>
                      {{ metadata.test.market.brier_score | number: "1.4-4" }}
                    </td>
                    <td>
                      {{
                        metadata.test.market.accuracy * 100 | number: "1.1-1"
                      }}%
                    </td>
                  </tr>
                  <tr>
                    <th>ML-modell</th>
                    <td>{{ metadata.test.ml.log_loss | number: "1.4-4" }}</td>
                    <td>
                      {{ metadata.test.ml.brier_score | number: "1.4-4" }}
                    </td>
                    <td>
                      {{ metadata.test.ml.accuracy * 100 | number: "1.1-1" }}%
                    </td>
                  </tr>
                </tbody>
              </table>
            </div>
            <p class="small muted">
              Brier är summan av kvadrerade fel över tre utfall (0–2).
              Sluttestets modell tränas på train + validation, före
              testperioden. Appens modell har därefter tränats om på all
              tillgänglig historik.
            </p>
            <details>
              <summary>Visa modellens featurelista</summary>
              <p class="small feature-list">
                {{ metadata.features.join(" · ") }}
              </p>
            </details>
          </section>
        }
      } @else {
        <section class="panel empty-state">
          <h3>
            {{
              store.status()?.datasetAvailable
                ? "Modell saknas"
                : "Dataset saknas"
            }}
          </h3>
          <p>
            Kör den dokumenterade import- och träningspipelinen. Under tiden
            används tydligt märkt marknadsfallback.
          </p>
          <code>python scripts/bootstrap_ml.py</code>
        </section>
      }
      @if (store.status()?.importReport?.failed?.length) {
        <p class="notice warning">
          {{ store.status()?.importReport?.failed?.length }} datafiler kunde
          inte hämtas. Detaljer finns i API:ts modellstatus och
          download_report.json.
        </p>
      }
    </details>
  `,
})
export class HistoryComponent {
  loadDetails(event: Event) {
    if ((event.target as HTMLDetailsElement).open)
      void this.store.loadModelStatus();
  }
  readonly store = inject(Store);
  readonly splits = [
    { key: "train", label: "TRAIN" },
    { key: "validation", label: "VALIDATION" },
    { key: "test", label: "TEST" },
  ] as const;
}
