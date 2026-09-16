import { DatePipe } from "../time";
import { Component, inject, OnInit, signal } from "@angular/core";
import { DecimalPipe } from "@angular/common";
import { FormsModule } from "@angular/forms";
import { HttpClient } from "@angular/common/http";
import { firstValueFrom } from "rxjs";
import { ArchiveDetail, ArchiveRow, OUTCOMES } from "../models";

@Component({
  selector: "app-draw-archive",
  standalone: true,
  imports: [DatePipe, DecimalPipe, FormsModule],
  template: `
    <section class="panel draw-archive">
      <div class="section-line">
        <div>
          <p class="eyebrow">VERKLIGA OMGÅNGAR</p>
          <h3>Stryktipsarkiv</h3>
        </div>
        <button (click)="load()">Uppdatera arkiv</button>
      </div>
      <p class="small muted">
        Officiellt facit och utdelning hålls separat från sparade prognoser.
        Systemen har inte lämnats in som spel.
      </p>
      @if (error()) {
        <p class="notice warning">{{ error() }}</p>
      }
      <div class="table-scroll">
        <table>
          <thead>
            <tr>
              <th>Omgång</th>
              <th>Datum</th>
              <th>Status</th>
              <th>Streck</th>
              <th>Sparat system</th>
              <th>Facit</th>
            </tr>
          </thead>
          <tbody>
            @for (draw of draws(); track draw.draw_number) {
              <tr>
                <td>
                  <button class="table-link" (click)="open(draw.draw_number)">
                    {{ draw.draw_number }}
                  </button>
                </td>
                <td>{{ draw.draw_date }}</td>
                <td>{{ statusLabel(draw.status) }}</td>
                <td>
                  {{ draw.snapshots }} snapshots
                  @if (!draw.pre_close_available) {
                    <span class="small muted">· inget pre-close</span>
                  }
                </td>
                <td>
                  {{
                    draw.system
                      ? draw.system.system.cost +
                        " kr · " +
                        draw.system.model.active_model
                      : "Ingen sparad prognos"
                  }}
                  @if (draw.system?.max_covered_correct != null) {
                    <br />Max {{ draw.system?.max_covered_correct }} täckta rätt
                  }
                </td>
                <td>
                  {{ draw.result_available ? "Tillgängligt" : "Inväntas" }}
                </td>
              </tr>
            } @empty {
              <tr>
                <td colspan="6">Inga omgångar har importerats ännu.</td>
              </tr>
            }
          </tbody>
        </table>
      </div>
      @if (detail(); as selected) {
        <section class="archive-detail">
          <div class="section-line">
            <h3>Omgång {{ selected.draw.draw_number }}</h3>
            <button (click)="detail.set(null)">Stäng omgång</button>
          </div>
          <label
            >Observationstid
            <select
              aria-label="Välj historiskt snapshot"
              [ngModel]="selection()"
              (ngModelChange)="select($event)"
            >
              <option value="pre_close">Sista före spelstopp</option>
              <option value="first">Första observation</option>
              <option value="24h">24 timmar före</option>
              <option value="latest">Senast arkiverad observation</option>
              @for (snapshot of selected.snapshots; track snapshot.id) {
                <option [value]="snapshot.recorded_at">
                  {{ snapshot.recorded_at | date: "yyyy-MM-dd HH:mm:ss" }}
                </option>
              }
            </select></label
          >
          <p class="small muted">
            Gräns {{ selected.as_of | date: "yyyy-MM-dd HH:mm:ss" }}. Endast
            input/prognoser registrerade senast då visas.
          </p>
          @if (selected.message) {
            <p class="notice warning">{{ selected.message }}</p>
          }
          @if (selection() === "latest") {
            <p class="notice">
              Senast arkiverade streck kan vara hämtade efter spelstopp. De
              används inte som historisk pre-match-prognos.
            </p>
          }
          <div class="table-scroll">
            <table>
              <thead>
                <tr>
                  <th>Match</th>
                  <th>Folket 1 / X / 2</th>
                  <th>Marknad 1 / X / 2</th>
                  <th>Sparad modell 1 / X / 2</th>
                  <th>Tecken</th>
                  <th>Facit</th>
                </tr>
              </thead>
              <tbody>
                @for (
                  match of selected.observation?.draw?.matches ??
                    selected.draw.matches;
                  track match.number
                ) {
                  <tr>
                    <td>
                      {{ match.number }}. {{ match.home_team }} –
                      {{ match.away_team }}
                    </td>
                    <td>
                      @if (selected.crowd[match.number]; as crowd) {
                        @for (o of outcomes; track o.key) {
                          <span
                            >{{ crowd.crowd[o.key] * 100 | number: "1.0-1" }}
                          </span>
                        }
                      } @else {
                        Ej tillgängligt
                      }
                    </td>
                    <td>
                      @if (selected.market[match.number]; as market) {
                        @for (o of outcomes; track o.key) {
                          <span
                            >{{ market.market[o.key] * 100 | number: "1.0-1" }}
                          </span>
                        }
                      } @else {
                        Ej tillgängligt
                      }
                    </td>
                    <td>
                      @if (prediction(match.number); as prediction) {
                        @for (o of outcomes; track o.key) {
                          <span
                            >{{
                              prediction.model[o.key] * 100 | number: "1.0-1"
                            }}
                          </span>
                        }
                      } @else {
                        Ingen sparad prognos
                      }
                    </td>
                    <td>
                      {{
                        prediction(match.number)?.recommendation?.join("") ??
                          "–"
                      }}
                    </td>
                    <td>{{ result(match.number) }}</td>
                  </tr>
                }
              </tbody>
            </table>
          </div>
          @if (selected.optimizer; as saved) {
            <p class="small muted">
              Modell {{ saved.model.active_model }} körd
              {{ saved.created_at | date: "dd/MM HH:mm:ss" }}. Prognosen
              behåller sina ursprungliga input-snapshots; senare observerade
              streck i tabellen har inte ändrat den.
            </p>
            <details>
              <summary>
                Ändringar sedan föregående system med samma budget/profil
              </summary>
              @for (change of saved.changes; track change.number) {
                <p>
                  Match {{ change.number }}: {{ change.previous.join("") }} →
                  {{ change.current.join("") }}
                </p>
              } @empty {
                <p>Inga registrerade ändringar.</p>
              }
            </details>
          }
          @if (selected.result; as result) {
            <h4>Officiell utdelning per vinnande rad</h4>
            <p class="small muted">
              Facit hämtades
              {{ result.recorded_at | date: "yyyy-MM-dd HH:mm" }} efter
              matcherna. Detta är efterhandsdata.
            </p>
            <div class="payout-grid">
              @for (p of result.payouts; track p.correct) {
                <div>
                  <strong>{{ p.correct }} rätt</strong>
                  <p>
                    {{
                      p.amount == null
                        ? "Ej tillgängligt"
                        : (p.amount | number: "1.0-2") + " kr"
                    }}
                  </p>
                  <small>{{
                    p.winners == null
                      ? "Antal vinnare saknas"
                      : p.winners + " vinnare"
                  }}</small>
                </div>
              } @empty {
                <p>Utdelning saknas i källan.</p>
              }
            </div>
          }
        </section>
      }
    </section>
  `,
})
export class DrawArchiveComponent implements OnInit {
  private readonly http = inject(HttpClient);
  readonly draws = signal<ArchiveRow[]>([]);
  readonly detail = signal<ArchiveDetail | null>(null);
  readonly error = signal("");
  readonly selection = signal("pre_close");
  readonly outcomes = OUTCOMES;
  ngOnInit() {
    void this.load();
  }
  async load() {
    try {
      this.draws.set(
        await firstValueFrom(
          this.http.get<ArchiveRow[]>("/api/stryktipset/draws"),
        ),
      );
      this.error.set("");
    } catch {
      this.error.set("Omgångsarkivet kunde inte hämtas.");
    }
  }
  async open(number: number) {
    this.selection.set("pre_close");
    await this.fetch(number);
  }
  async select(value: string) {
    this.selection.set(value);
    const n = this.detail()?.draw.draw_number;
    if (n) await this.fetch(n);
  }
  private async fetch(n: number) {
    const s = this.selection();
    const params: Record<string, string> = [
      "first",
      "24h",
      "pre_close",
      "latest",
    ].includes(s)
      ? { selection: s }
      : { as_of: s };
    try {
      this.detail.set(
        await firstValueFrom(
          this.http.get<ArchiveDetail>(`/api/stryktipset/draws/${n}`, {
            params,
          }),
        ),
      );
    } catch {
      this.error.set("Omgångens snapshots kunde inte hämtas.");
    }
  }
  prediction(number: number) {
    return this.detail()?.optimizer?.analysis.matches.find(
      (m) => m.number === number,
    );
  }
  result(number: number) {
    const r = this.detail()?.result?.matches.find((m) => m.number === number);
    return r?.outcome
      ? r.outcome +
          (r.home_goals != null && r.away_goals != null
            ? " (" + r.home_goals + "–" + r.away_goals + ")"
            : "")
      : "Ej tillgängligt";
  }
  statusLabel(s: string) {
    return (
      (
        {
          open: "Öppen",
          upcoming: "Kommande",
          closed: "Stängd",
          completed: "Avslutad",
        } as Record<string, string>
      )[s] ?? s
    );
  }
}
