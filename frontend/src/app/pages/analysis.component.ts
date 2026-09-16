import { Component, computed, inject } from "@angular/core";
import { DecimalPipe } from "@angular/common";
import { Store } from "../store";
import { OUTCOMES } from "../models";

@Component({
  standalone: true,
  imports: [DecimalPipe],
  template: `
    <div class="page-intro">
      <p class="eyebrow">MODELLEN & KOLLEKTIVET</p>
      <h2>Där vi skiljer oss från Svenska Folket</h2>
      <p class="muted">
        Alla 39 tecken, sorterade efter störst positiv skillnad mot Svenska
        Folket. En positiv skillnad betyder understreckat relativt prognosen.
      </p>
    </div>
    <section class="insights" aria-label="Tre perspektiv på strecken">
      @for(group of highlights();track group.title){<article class="panel insight-card"><h3>{{group.title}}</h3>
      @for(row of group.rows;track row.id){<p><button class="text-button" (click)="store.selectedMatch.set(row.match)">{{row.match.homeTeam}} – {{row.match.awayTeam}} · {{row.sign}}</button><br/>Vår sannolikhet {{row.model*100|number:'1.0-0'}} % · Folket {{row.crowd*100|number:'1.0-0'}} %</p>}
      </article>}
    </section>
    @if (store.dataMode() === "live") {
      <section class="panel crowd-movements">
        <h3>Största streckrörelser</h3>
        <p class="small muted">
          Förändring sedan första registrerade observation. Modellens
          sannolikheter ändras inte av streckrörelser.
        </p>
        @for (move of movements(); track move.id) {
          <p>
            <strong>{{ move.number }}. {{ move.team }} {{ move.sign }}</strong>
            · {{ move.delta > 0 ? "+" : ""
            }}{{ move.delta * 100 | number: "1.1-1" }} pp
          </p>
        } @empty {
          <p class="small muted">
            Inga observerade förändringar ännu. Minst två snapshots krävs.
          </p>
        }
      </section>
    }
    <section class="panel table-scroll">
      <table>
        <caption>
          Sannolikhet, streck och spelvärde
        </caption>
        <thead>
          <tr>
            <th>Match</th>
            <th>Tecken</th>
            <th>Vår sannolikhet</th>
            <th>Marknad</th>
            <th>Folket</th>
            <th>Skillnad (pp)</th>
            <th>Spelvärdesindex</th>
          </tr>
        </thead>
        <tbody>
          @for (row of rows(); track row.id) {
            <tr>
              <td>
                <button
                  class="table-link"
                  (click)="store.selectedMatch.set(row.match)"
                >
                  {{ row.match.number }}. {{ row.match.homeTeam }} –
                  {{ row.match.awayTeam }}
                </button>
              </td>
              <td>
                <strong>{{ row.sign }}</strong>
              </td>
              <td>{{ row.model * 100 | number: "1.1-1" }}%</td>
              <td>{{ row.market * 100 | number: "1.1-1" }}%</td>
              <td>{{ row.crowd * 100 | number: "1.1-1" }}%</td>
              <td [class.value-cell]="row.edge > 0">
                {{ row.edge > 0 ? "+" : ""
                }}{{ row.edge * 100 | number: "1.1-1" }}
              </td>
              <td>{{ row.value | number: "1.2-2" }}</td>
            </tr>
          }
        </tbody>
      </table>
    </section>
    <p class="small muted">
      Edge är procentenheter. Värdeindex = prognos / streck, med ett golv på
      0,5% för streck. Ett högt index är inte en garanti för vinst.
    </p>
  `,
})
export class AnalysisComponent {
  readonly highlights=computed(()=>[{title:'Största spelvärden',rows:[...this.rows()].sort((a,b)=>b.value-a.value).slice(0,3)},{title:'Mest överstreckade',rows:[...this.rows()].reverse().slice(0,3)},{title:'Mest understreckade',rows:this.rows().slice(0,3)}]);
  readonly store = inject(Store);
  readonly movements = computed(() =>
    (this.store.live()?.movement ?? [])
      .flatMap((m) =>
        m.since_first
          ? OUTCOMES.map((o) => ({
              id: m.number + "-" + o.sign,
              number: m.number,
              sign: o.sign,
              delta: m.since_first![o.key],
              team:
                this.store
                  .live()
                  ?.draw?.matches.find((x) => x.number === m.number)
                  ?.home_team ?? "",
            }))
          : [],
      )
      .filter((m) => Math.abs(m.delta) > 1e-9)
      .sort((a, b) => Math.abs(b.delta) - Math.abs(a.delta))
      .slice(0, 5),
  );
  readonly rows = computed(() =>
    (this.store.analysis()?.matches ?? [])
      .flatMap((match) =>
        OUTCOMES.map((o) => ({
          id: `${match.number}-${o.sign}`,
          match,
          sign: o.sign,
          model: match.model[o.key],
          market: match.market[o.key],
          crowd: match.crowd[o.key],
          edge: match.edge[o.key],
          value: match.value[o.key],
        })),
      )
      .sort((a, b) => b.edge - a.edge),
  );
}
