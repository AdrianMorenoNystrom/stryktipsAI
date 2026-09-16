import { Component, inject } from "@angular/core";
import { FormsModule } from "@angular/forms";
import { Store } from "../store";
@Component({
  selector: "app-budget",
  standalone: true,
  imports: [FormsModule],
  template: ` <div class="budget-controls">
    <div class="budget-main">
      <h3>Hur stort system vill du spela?</h3>
      <div class="segmented" aria-label="Välj budget">
        @for (amount of store.config()?.budgetPresets ?? []; track amount) {
          <button
            [class.active]="store.budget() === amount"
            [attr.aria-pressed]="store.budget() === amount"
            (click)="store.setBudget(amount)"
          >
            {{ amount }} kr
          </button>
        }
      </div>
      <p class="small muted">
        Budgeten är ett tak. Den faktiska kostnaden visas ovan.
      </p>
    </div>
    <details class="profile-options">
      <summary>Fler alternativ</summary>
      <label class="custom-budget"
        >Egen budget<input
          aria-label="Egen budget"
          type="number"
          [min]="store.config()?.costPerRow ?? 1"
          max="1000000"
          [ngModel]="store.budget()"
          (change)="store.setBudget(+$any($event.target).value)"
      /></label>
      <div class="mode-control">
        <div class="segmented" aria-label="Välj systemprofil">
          @for (mode of modes; track mode.key) {
            <button
              [class.active]="store.mode() === mode.key"
              [attr.aria-pressed]="store.mode() === mode.key"
              (click)="store.setMode(mode.key)"
            >
              {{ mode.label }}
            </button>
          }
        </div>
        @for (mode of modes; track mode.key) {
          @if (store.mode() === mode.key) {
            <p class="small">{{ mode.description }}</p>
          }
        }
      </div>
    </details>
  </div>`,
})
export class BudgetComponent {
  readonly store = inject(Store);
  readonly modes = [
    {
      key: "optimal",
      label: "Rekommenderad",
      description:
        "Balanserar sannolikhet och hur Svenska Folket har streckat.",
    },
    {
      key: "safe",
      label: "Säkrare",
      description:
        "Prioriterar de mest sannolika utfallen mer. Utfallet är fortfarande osäkert.",
    },
    {
      key: "value",
      label: "Mer värde",
      description:
        "Tar större hänsyn till tecken som modellen bedömer högre än Svenska Folket.",
    },
  ] as const;
}
