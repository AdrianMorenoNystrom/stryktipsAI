import { DatePipe } from "../time";
import { Component, inject, input, OnInit, signal } from "@angular/core";
import { DecimalPipe } from "@angular/common";
import { HttpClient } from "@angular/common/http";
import { firstValueFrom } from "rxjs";
import { Store } from "../store";
import { CrowdObservation, Movement, OUTCOMES } from "../models";

@Component({
  selector: "app-crowd-history",
  standalone: true,
  imports: [DatePipe, DecimalPipe],
  template: `
    <section class="crowd-history">
      <h3>Svenska Folket över tid</h3>
      <p class="small muted">
        Observerade streck. Streckrörelser ändrar inte modellens sannolikheter.
      </p>
      @if (error()) {
        <p class="notice warning">{{ error() }}</p>
      }
      @if (data(); as saved) {
        <div class="table-scroll">
          <table>
            <thead>
              <tr>
                <th>Registrerad</th>
                <th>1</th>
                <th>X</th>
                <th>2</th>
              </tr>
            </thead>
            <tbody>
              @for (row of saved.history; track row.id) {
                <tr>
                  <td>{{ row.recorded_at | date: "dd/MM HH:mm:ss" }}</td>
                  <td>{{ row.crowd.home * 100 | number: "1.0-1" }}</td>
                  <td>{{ row.crowd.draw * 100 | number: "1.0-1" }}</td>
                  <td>{{ row.crowd.away * 100 | number: "1.0-1" }}</td>
                </tr>
              }
            </tbody>
          </table>
        </div>
        @if (saved.history.length < 2) {
          <p class="small muted">
            {{ saved.history.length }} observation. Ingen streckrörelse kan
            beräknas ännu.
          </p>
        }
        @if (saved.movement.since_first; as change) {
          <p class="small">
            Sedan första:
            @for (o of outcomes; track o.key) {
              <span
                >{{ o.sign }} {{ change[o.key] > 0 ? "+" : ""
                }}{{ change[o.key] * 100 | number: "1.1-1" }} pp ·
              </span>
            }
          </p>
        }
        @if (saved.movement.since_previous; as change) {
          <p class="small">
            Sedan föregående:
            @for (o of outcomes; track o.key) {
              <span
                >{{ o.sign }} {{ change[o.key] > 0 ? "+" : ""
                }}{{ change[o.key] * 100 | number: "1.1-1" }} pp ·
              </span>
            }
          </p>
        }
        <details>
          <summary>Käll- och hämtningstider</summary>
          @for (row of saved.history; track row.id) {
            <p class="small">
              Hämtad {{ row.retrieved_at | date: "dd/MM HH:mm:ss" }} · Källa
              uppdaterad
              {{
                row.source_updated_at
                  ? (row.source_updated_at | date: "dd/MM HH:mm:ss")
                  : "okänd"
              }}
              ·
              {{
                row.is_pre_close_snapshot
                  ? "Observerad före spelstopp"
                  : "Ej pre-close-underlag"
              }}
            </p>
          }
        </details>
      }
    </section>
  `,
})
export class CrowdHistoryComponent implements OnInit {
  readonly number = input.required<number>();
  readonly store = inject(Store);
  private readonly http = inject(HttpClient);
  readonly outcomes = OUTCOMES;
  readonly error = signal("");
  readonly data = signal<{
    history: CrowdObservation[];
    movement: Movement;
  } | null>(null);
  async ngOnInit() {
    const draw = this.store.analysis()?.drawNumber;
    if (!draw) return;
    try {
      this.data.set(
        await firstValueFrom(
          this.http.get<{ history: CrowdObservation[]; movement: Movement }>(
            `/api/stryktipset/draws/${draw}/matches/${this.number()}/crowd`,
          ),
        ),
      );
    } catch {
      this.error.set("Streckhistoriken kunde inte hämtas.");
    }
  }
}
