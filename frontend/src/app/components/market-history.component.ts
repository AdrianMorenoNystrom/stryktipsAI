import {
  Component,
  inject,
  input,
  OnInit,
  signal,
  computed,
} from "@angular/core";
import { HttpClient } from "@angular/common/http";
import { DecimalPipe } from "@angular/common";
import { DatePipe } from "../time";
import { firstValueFrom } from "rxjs";
import { Store } from "../store";
import { Probabilities, Outcome, OUTCOMES } from "../models";
import { CrowdHistoryComponent } from "./crowd-history.component";
interface Observation {
  retrieved_at: string;
  recorded_at: string;
  consensus?: Probabilities;
  crowd?: Probabilities;
}
interface History {
  market: Observation[];
  crowd: Observation[];
  predictions: { id: string; predicted_at: string; model: Probabilities }[];
}
@Component({
  selector: "app-market-history",
  standalone: true,
  imports: [DecimalPipe, DatePipe, CrowdHistoryComponent],
  template: ` <h3>Folket och marknaden över tid</h3>
    <div class="segmented" aria-label="Tecken i historiken">
      @for (o of outcomes; track o.key) {
        <button
          [attr.aria-pressed]="outcome() === o.key"
          [class.active]="outcome() === o.key"
          (click)="outcome.set(o.key)"
        >
          {{ o.sign }}
        </button>
      }
    </div>
    @if (error()) {
      <p role="status">{{ error() }}</p>
    }
    @if (data(); as h) {
      @if (h.market.length) {
        <p class="small">
          Heldragen linje: Svenska Folket. Streckad linje: bookmakerkonsensus.
          Endast sparade observationer visas.
        </p>
        <svg
          viewBox="0 0 560 230"
          class="movement-chart"
          role="img"
          aria-label="Svenska Folket och bookmakerkonsensus över registrerad tid"
        >
          <line x1="38" x2="545" y1="190" y2="190" stroke="#dce4eb" />
          <text x="0" y="25">100 %</text>
          <text x="0" y="195">0 %</text>
          <polyline
            [attr.points]="points(h.crowd, 'crowd')"
            fill="none"
            stroke="#00427A"
            stroke-width="3"
          />
          <polyline
            [attr.points]="points(h.market, 'consensus')"
            fill="none"
            stroke="#8A3C36"
            stroke-width="3"
            stroke-dasharray="7 4"
          />
          <text x="38" y="222">{{ bounds()[0] | date: "dd/MM HH:mm" }}</text>
          <text x="400" y="222">{{ bounds()[1] | date: "dd/MM HH:mm" }}</text>
        </svg>
        @if (comparison(); as c) {
          <p>
            Svenska Folket har ändrats {{ c.crowd > 0 ? "+" : ""
            }}{{ c.crowd * 100 | number: "1.1-1" }} procentenheter. Marknaden
            har ändrats {{ c.market > 0 ? "+" : ""
            }}{{ c.market * 100 | number: "1.1-1" }} under samma observerade
            period. Det beskriver rörelse, inte vad som orsakat den.
          </p>
        } @else {
          <p>
            Fler observationer under en gemensam period behövs för att jämföra
            rörelser.
          </p>
        }
      } @else {
        <p class="notice">
          Bookmakerhistorik saknas. Inga konsensusvärden har konstruerats från
          Svenska Spels odds.
        </p>
      }
      <app-crowd-history [number]="number()" />
      <details>
        <summary>Tidigare sparade sannolikheter</summary>
        <table>
          <thead>
            <tr>
              <th>Tid</th>
              <th>1</th>
              <th>X</th>
              <th>2</th>
            </tr>
          </thead>
          <tbody>
            @for (p of h.predictions; track p.id) {
              <tr>
                <td>{{ p.predicted_at | date: "dd/MM HH:mm:ss" }}</td>
                <td>{{ p.model.home * 100 | number: "1.1-1" }}</td>
                <td>{{ p.model.draw * 100 | number: "1.1-1" }}</td>
                <td>{{ p.model.away * 100 | number: "1.1-1" }}</td>
              </tr>
            } @empty {
              <tr>
                <td colspan="4">Ingen sparad prognos.</td>
              </tr>
            }
          </tbody>
        </table>
      </details>
    }`,
})
export class MarketHistoryComponent implements OnInit {
  readonly number = input.required<number>();
  readonly store = inject(Store);
  readonly http = inject(HttpClient);
  readonly data = signal<History | null>(null);
  readonly error = signal("");
  readonly outcome = signal<Outcome>("home");
  readonly outcomes = OUTCOMES;
  readonly bounds = computed(() => {
    const rows = [
      ...(this.data()?.market ?? []),
      ...(this.data()?.crowd ?? []),
    ].map((o) => Date.parse(o.retrieved_at));
    return rows.length ? [Math.min(...rows), Math.max(...rows)] : [0, 1];
  });
  readonly comparison = computed(() => {
    const h = this.data();
    if (!h || h.market.length < 2 || h.crowd.length < 2) return null;
    const first = Math.max(
      Date.parse(h.market[0].retrieved_at),
      Date.parse(h.crowd[0].retrieved_at),
    );
    const last = Math.min(
      Date.parse(h.market.at(-1)!.retrieved_at),
      Date.parse(h.crowd.at(-1)!.retrieved_at),
    );
    if (last <= first) return null;
    const change = (rows: Observation[], key: "crowd" | "consensus") => {
      const start = rows
        .filter((o) => Date.parse(o.retrieved_at) <= first)
        .at(-1)!;
      const end = rows
        .filter((o) => Date.parse(o.retrieved_at) <= last)
        .at(-1)!;
      return end[key]![this.outcome()] - start[key]![this.outcome()];
    };
    return {
      crowd: change(h.crowd, "crowd"),
      market: change(h.market, "consensus"),
    };
  });
  async ngOnInit() {
    try {
      this.data.set(
        await firstValueFrom(
          this.http.get<History>(
            `/api/stryktipset/draws/${this.store.analysis()?.drawNumber}/matches/${this.number()}/market`,
          ),
        ),
      );
    } catch {
      this.error.set("Historiken kunde inte hämtas.");
    }
  }
  points(rows: Observation[], key: "crowd" | "consensus") {
    const [a, b] = this.bounds();
    return rows
      .map(
        (r) =>
          `${38 + (507 * (Date.parse(r.retrieved_at) - a)) / Math.max(1, b - a)},${190 - 170 * r[key]![this.outcome()]}`,
      )
      .join(" ");
  }
}
