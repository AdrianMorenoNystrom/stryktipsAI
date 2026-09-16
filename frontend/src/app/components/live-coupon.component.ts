import { DatePipe } from "../time";
import { Component, inject, signal } from "@angular/core";
import { DecimalPipe } from "@angular/common";
import { FormsModule } from "@angular/forms";
import { HttpClient } from "@angular/common/http";
import { firstValueFrom } from "rxjs";
import { Store } from "../store";
import { LiveState, OUTCOMES, Probabilities } from "../models";

@Component({
  selector: "app-live-coupon",
  standalone: true,
  imports: [DatePipe, DecimalPipe, FormsModule],
  template: `
    <section class="live-controls" aria-label="Kupongkälla">
      <div class="live-actions">
        <button
          [class.primary]="store.dataMode() === 'live'"
          (click)="store.loadCurrent()"
          [disabled]="store.loading()"
        >
          Aktuell kupong
        </button>
        @if (!store.production) {
          <button (click)="manual()" [disabled]="store.loading()">
            Manuell / demo
          </button>
        }
        @if (store.dataMode() === "live") {
          <button
            (click)="store.loadCurrent(store.live()?.draw?.draw_number, true)"
            [disabled]="store.loading()"
          >
            Uppdatera
          </button>
          @if ((store.live()?.available_draws?.length ?? 0) > 1) {
            <label
              >Omgång
              <select
                aria-label="Välj omgång"
                [ngModel]="store.live()?.draw?.draw_number"
                (ngModelChange)="store.loadCurrent(+$event)"
              >
                @for (
                  draw of store.live()?.available_draws;
                  track draw.draw_number
                ) {
                  <option [ngValue]="draw.draw_number">
                    {{ draw.draw_number }} ·
                    {{ draw.sales_close_at | date: "dd/MM HH:mm" }}
                  </option>
                }
              </select></label
            >
          }
        }
      </div>
      @if (store.dataMode() === "live" && store.live(); as live) {
        @if (live.stale) {
          <p class="notice warning" role="status">
            Live-data kunde inte uppdateras. Visar senast sparad data från
            {{ live.draw?.retrieved_at | date: "dd/MM HH:mm" }}.
          </p>
        }
        @if (live.draw; as draw) {
          <p class="small muted">
            Svenska Folket: observerat hos Svenska Spel · Hämtat
            {{ draw.retrieved_at | date: "dd/MM HH:mm" }}. Odds:
            {{
              live.manual_odds_matches
                ? live.manual_odds_matches + " manuellt inmatade matcher"
                : oddsLabel()
            }}. Prognos: uppskattad. Edge och värde: beräknade.
          </p>
          <details class="source-details">
            <summary>Underlag, lagmappning och manuella odds</summary>
            <p class="small">
              {{ live.mapping?.mapped }} /
              {{ live.mapping?.references }} lagreferenser mappade.
              {{ live.mapping?.supported_model_matches }} / 13 matcher har
              tränad ligatäckning. Provider: {{ live.health.status }}.
            </p>
            <p class="small">
              Bookmakerkonsensus används när tillräckligt många kompletta odds
              finns. Annars används märkt sparad konsensus, Svenska Spels
              separata odds eller manuella odds. Folkstreck används aldrig som
              marknadsodds.
            </p>
            @if (live.mapping?.unmapped?.length) {
              <p class="notice warning">
                Omappade lag: {{ live.mapping?.unmapped?.join(", ") }}.
                Marknadsodds kan användas som tydligt märkt fallback.
              </p>
            }
            <a [href]="draw.source" target="_blank" rel="noopener noreferrer"
              >Visa originalkälla ↗</a
            >
            @if (!store.production) { <p>
              <button (click)="openOdds()">
                Ange eller komplettera marknadsodds
              </button>
            </p> }
          </details>
          @if (!live.analysis_ready) {
            <section class="panel pending-coupon">
              <h2>Kupongen behöver kompletteras</h2>
              <p>
                Ingen optimal rad visas innan alla 13 matcher har giltiga
                underlag.
              </p>
              @for (issue of live.issues; track $index) {
                <p class="small warning">{{ issue }}</p>
              }
              <div class="table-scroll">
                <table>
                  <thead>
                    <tr>
                      <th>Match</th>
                      <th>Svenska Folket 1 / X / 2</th>
                      <th>Odds</th>
                    </tr>
                  </thead>
                  <tbody>
                    @for (m of draw.matches; track m.number) {
                      <tr>
                        <td>
                          {{ m.number }}. {{ m.home_team }} – {{ m.away_team }}
                        </td>
                        <td>
                          @if (m.crowd; as q) {
                            {{ q.home * 100 | number: "1.0-1" }} /
                            {{ q.draw * 100 | number: "1.0-1" }} /
                            {{ q.away * 100 | number: "1.0-1" }}
                          } @else {
                            Ej tillgängligt
                          }
                        </td>
                        <td>
                          {{
                            m.market_odds ? "Observerade" : "Ej tillgängligt"
                          }}
                        </td>
                      </tr>
                    }
                  </tbody>
                </table>
              </div>
              @if (!store.production) { <button (click)="openOdds()">Komplettera odds</button> }
            </section>
          }
          @if (editingOdds()) {
            <form class="panel live-odds" (ngSubmit)="saveOdds()">
              <h3>Manuella marknadsodds</h3>
              <p class="small muted">
                Endast ändrade, fullständiga 1/X/2-odds sparas med aktuell
                registreringstid. Strecken ändras inte.
              </p>
              @for (m of draw.matches; track m.number) {
                <div class="live-odds-row">
                  <span
                    >{{ m.number }}. {{ m.home_team }} – {{ m.away_team }}</span
                  >
                  @for (o of outcomes; track o.key) {
                    <label
                      >{{ o.sign
                      }}<input
                        type="number"
                        min="1.01"
                        max="10000"
                        step="0.01"
                        [name]="'live-odds-' + m.number + '-' + o.key"
                        [attr.aria-label]="
                          'Match ' + m.number + ', manuella odds ' + o.sign
                        "
                        [(ngModel)]="odds[m.number][o.key]"
                    /></label>
                  }
                </div>
              }
              @if (oddsError()) {
                <p class="notice error" role="alert">{{ oddsError() }}</p>
              }
              <button class="primary" type="submit">
                Spara odds och analysera</button
              ><button type="button" (click)="editingOdds.set(false)">
                Stäng
              </button>
            </form>
          }
        }
      }
    </section>
  `,
})
export class LiveCouponComponent {
  oddsLabel(): string {
    const matches = this.store.analysis()?.matches ?? [];
    const count = matches.filter(
      (m) =>
        m.marketSource === "bookmaker_consensus" ||
        m.marketSource === "cached_consensus",
    ).length;
    return count
      ? count + " matcher med bookmakerkonsensus; övriga har märkt fallback"
      : "Svenska Spels kupongflöde · fallback";
  }
  readonly store = inject(Store);
  private readonly http = inject(HttpClient);
  readonly outcomes = OUTCOMES;
  readonly editingOdds = signal(false);
  readonly oddsError = signal("");
  odds: Record<number, Probabilities> = {};
  private original: Record<number, Probabilities> = {};
  async manual() {
    await this.store.loadDemo(
      "Välj Kupong → Redigera → Ny tom kupong för en egen manuell kupong.",
    );
  }
  openOdds() {
    for (const m of this.store.live()?.draw?.matches ?? [])
      this.odds[m.number] = structuredClone(
        this.store.coupon()?.matches.find((c) => c.number === m.number)
          ?.marketOdds ??
          m.market_odds ?? { home: 0, draw: 0, away: 0 },
      );
    this.original = structuredClone(this.odds);
    this.editingOdds.set(true);
  }
  async saveOdds() {
    const draw = this.store.live()?.draw;
    if (!draw) return;
    const changed = Object.fromEntries(
      Object.entries(this.odds).filter(
        ([n, v]) => JSON.stringify(v) !== JSON.stringify(this.original[+n]),
      ),
    );
    if (
      !Object.keys(changed).length ||
      Object.values(changed).some((v) =>
        Object.values(v).some((p) => !Number.isFinite(p) || p <= 1),
      )
    ) {
      this.oddsError.set(
        "Ändra minst en match och ange tre giltiga decimalodds.",
      );
      return;
    }
    try {
      const state = await firstValueFrom(
        this.http.post<LiveState>(
          `/api/stryktipset/draws/${draw.draw_number}/odds`,
          { odds: changed },
        ),
      );
      this.store.live.set(state);
      this.store.coupon.set(state.coupon);
      this.editingOdds.set(false);
      if (state.analysis_ready) await this.store.analyze(state.coupon);
    } catch (error) {
      this.oddsError.set(this.store.message(error));
    }
  }
}
