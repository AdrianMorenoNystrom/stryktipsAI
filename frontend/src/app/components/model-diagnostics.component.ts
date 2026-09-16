import { DatePipe } from "../time";
import { Component, input } from "@angular/core";
import { DecimalPipe, KeyValuePipe } from "@angular/common";
import { ModelMetadata } from "../models";

@Component({
  selector: "app-model-diagnostics",
  standalone: true,
  imports: [DatePipe, DecimalPipe, KeyValuePipe],
  template: `
    @if (metadata().evaluation; as evaluation) {
      <section class="panel history-panel">
        <div class="section-line">
          <div>
            <p class="eyebrow">AKTIV MODELL</p>
            <h3>{{ metadata().activeModelLabel }}</h3>
          </div>
          <span class="tag">MARKET ANCHOR · V2</span>
        </div>
        <p>{{ evaluation.selection.reason }}</p>
        <p class="small muted">
          Tränad {{ metadata().trained_at | date: "yyyy-MM-dd HH:mm" }} · data
          till {{ metadata().data_through }}. Nyheter påverkar inte
          sannolikheterna.
        </p>
        <div class="table-scroll">
          <table>
            <caption>
              Walk-forward · 2020/21–2025/26
            </caption>
            <thead>
              <tr>
                <th>Prognos</th>
                <th>Log Loss ↓</th>
                <th>Brier ↓</th>
                <th>ECE ↓</th>
                <th>Accuracy</th>
              </tr>
            </thead>
            <tbody>
              @for (model of models; track model.key) {
                <tr>
                  <th>{{ model.label }}</th>
                  <td>
                    {{
                      evaluation.overall[model.key].log_loss | number: "1.6-6"
                    }}
                  </td>
                  <td>
                    {{
                      evaluation.overall[model.key].brier_score
                        | number: "1.6-6"
                    }}
                  </td>
                  <td>
                    {{
                      (evaluation.overall[model.key].ece ?? 0) * 100
                        | number: "1.2-2"
                    }}%
                  </td>
                  <td>
                    {{
                      evaluation.overall[model.key].accuracy * 100
                        | number: "1.2-2"
                    }}%
                  </td>
                </tr>
              }
            </tbody>
          </table>
        </div>
        <p class="small muted">
          V2-kandidat: {{ evaluation.selection.v2_candidate }}. Variantvalet
          använder {{ evaluation.selection.development_seasons.join(", ") }}. De
          resultaten är modellvalsunderlag; auditsäsongen
          {{ evaluation.auditSeason }} visas separat. ECE är genomsnittligt
          klassvist kalibreringsfel i 20 lika breda bin.
        </p>
        <details>
          <summary>Separat audit · {{ evaluation.auditSeason }}</summary>
          <table>
            <thead>
              <tr>
                <th>Prognos</th>
                <th>Log Loss</th>
                <th>Brier</th>
              </tr>
            </thead>
            <tbody>
              @for (model of models; track model.key) {
                <tr>
                  <th>{{ model.label }}</th>
                  <td>
                    {{ evaluation.audit[model.key].log_loss | number: "1.6-6" }}
                  </td>
                  <td>
                    {{
                      evaluation.audit[model.key].brier_score | number: "1.6-6"
                    }}
                  </td>
                </tr>
              }
            </tbody>
          </table>
        </details>
        <details open>
          <summary>Resultat per liga</summary>
          <div class="table-scroll">
            <table>
              <thead>
                <tr>
                  <th>Liga</th>
                  <th>Prognos</th>
                  <th>Log Loss</th>
                  <th>Brier</th>
                  <th>ECE</th>
                  <th>Accuracy</th>
                </tr>
              </thead>
              <tbody>
                @for (
                  league of evaluation.byLeague | keyvalue;
                  track league.key
                ) {
                  @for (model of models; track model.key) {
                    <tr>
                      <th>{{ leagueName(league.key) }}</th>
                      <td>{{ model.label }}</td>
                      <td>
                        {{ league.value[model.key].log_loss | number: "1.5-5" }}
                      </td>
                      <td>
                        {{
                          league.value[model.key].brier_score | number: "1.5-5"
                        }}
                      </td>
                      <td>
                        {{
                          (league.value[model.key].ece ?? 0) * 100
                            | number: "1.2-2"
                        }}%
                      </td>
                      <td>
                        {{
                          league.value[model.key].accuracy * 100
                            | number: "1.2-2"
                        }}%
                      </td>
                    </tr>
                  }
                }
              </tbody>
            </table>
          </div>
        </details>
        <details>
          <summary>Stabilitet över säsonger</summary>
          <div class="table-scroll">
            <table>
              <thead>
                <tr>
                  <th>Säsong</th>
                  @for (model of models; track model.key) {
                    <th>{{ model.label }} · LL</th>
                  }
                </tr>
              </thead>
              <tbody>
                @for (
                  season of evaluation.bySeason | keyvalue;
                  track season.key
                ) {
                  <tr>
                    <th>{{ season.key }}</th>
                    @for (model of models; track model.key) {
                      <td>
                        {{ season.value[model.key].log_loss | number: "1.5-5" }}
                      </td>
                    }
                  </tr>
                }
              </tbody>
            </table>
          </div>
        </details>
        <details>
          <summary>Ablation · utvecklingssäsonger</summary>
          <p class="small muted">
            Negativ skillnad är bättre än marknaden. Alla varianter använder
            samma testmatcher.
          </p>
          <div class="table-scroll">
            <table>
              <thead>
                <tr>
                  <th>Variant</th>
                  <th>Δ Log Loss</th>
                  <th>Δ Brier</th>
                  <th>Vunna säsonger</th>
                </tr>
              </thead>
              <tbody>
                @for (
                  variant of evaluation.developmentAblation | keyvalue;
                  track variant.key
                ) {
                  <tr>
                    <th>{{ variant.key }}</th>
                    <td>
                      {{ variant.value.delta_log_loss | number: "1.6-6" }}
                    </td>
                    <td>{{ variant.value.delta_brier | number: "1.6-6" }}</td>
                    <td>{{ variant.value.winning_seasons }}</td>
                  </tr>
                }
              </tbody>
            </table>
          </div>
        </details>
        <details>
          <summary>När modellen avviker från marknaden</summary>
          <p class="small muted">
            Största absoluta skillnad för något tecken. Positiv Δ Log Loss
            betyder sämre än marknaden på just dessa matcher.
          </p>
          <table>
            <thead>
              <tr>
                <th>Skillnad</th>
                <th>Matcher</th>
                <th>V2 Δ Log Loss</th>
              </tr>
            </thead>
            <tbody>
              @for (
                bucket of evaluation.disagreement["v2"] | keyvalue;
                track bucket.key
              ) {
                <tr>
                  <th>{{ bucket.key }}</th>
                  <td>{{ bucket.value.matches }}</td>
                  <td>
                    {{
                      bucket.value.delta_log_loss === null
                        ? "—"
                        : (bucket.value.delta_log_loss | number: "1.6-6")
                    }}
                  </td>
                </tr>
              }
            </tbody>
          </table>
        </details>
        <details>
          <summary>Matchtyper och marknadsfavoriter</summary>
          <div class="table-scroll">
            <table>
              <thead>
                <tr>
                  <th>Grupp</th>
                  <th>Matcher</th>
                  <th>Marknad LL</th>
                  <th>V2 LL</th>
                </tr>
              </thead>
              <tbody>
                @for (
                  bucket of evaluation.byMarketBucket | keyvalue;
                  track bucket.key
                ) {
                  <tr>
                    <th>{{ bucket.key }}</th>
                    <td>{{ bucket.value["market"]?.matches ?? 0 }}</td>
                    <td>
                      {{ bucket.value["market"]?.log_loss | number: "1.5-5" }}
                    </td>
                    <td>
                      {{ bucket.value["v2"]?.log_loss | number: "1.5-5" }}
                    </td>
                  </tr>
                }
              </tbody>
            </table>
          </div>
        </details>
        <details>
          <summary>Kalibrering per utfall · Model v2</summary>
          @for (
            bins of evaluation.overall["v2"].calibration ?? [];
            track $index;
            let index = $index
          ) {
            <h3>{{ outcomes[index] }}</h3>
            <table>
              <thead>
                <tr>
                  <th>Intervall</th>
                  <th>Prognos</th>
                  <th>Utfall</th>
                  <th>Antal</th>
                </tr>
              </thead>
              <tbody>
                @for (bin of bins; track bin.lower) {
                  <tr>
                    <td>
                      {{ bin.lower * 100 | number: "1.0-0" }}–{{
                        bin.upper * 100 | number: "1.0-0"
                      }}%
                    </td>
                    <td>{{ bin.predicted * 100 | number: "1.1-1" }}%</td>
                    <td>{{ bin.observed * 100 | number: "1.1-1" }}%</td>
                    <td>{{ bin.count }}</td>
                  </tr>
                }
              </tbody>
            </table>
          }
        </details>
      </section>
    }
  `,
})
export class ModelDiagnosticsComponent {
  readonly metadata = input.required<ModelMetadata>();
  readonly models = [
    { key: "market", label: "Marknad" },
    { key: "v1", label: "Model v1" },
    { key: "v2", label: "Model v2" },
  ];
  readonly outcomes = ["Hemma (1)", "Oavgjort (X)", "Borta (2)"];
  leagueName(key: string): string {
    return (
      (
        {
          E0: "Premier League",
          E1: "Championship",
          E2: "League One",
        } as Record<string, string>
      )[key] ?? key
    );
  }
}
