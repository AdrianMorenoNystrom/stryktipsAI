import { Pipe, PipeTransform } from "@angular/core";

@Pipe({ name: "date", standalone: true })
export class DatePipe implements PipeTransform {
  transform(
    value: string | number | Date | null | undefined,
    format = "yyyy-MM-dd",
  ): string {
    if (value == null || value === "") return "";
    const date = new Date(value);
    if (Number.isNaN(date.getTime())) return "";
    const parts = Object.fromEntries(
      new Intl.DateTimeFormat("sv-SE", {
        timeZone: "Europe/Stockholm",
        year: "numeric",
        month: "2-digit",
        day: "2-digit",
        hour: "2-digit",
        minute: "2-digit",
        second: "2-digit",
        hourCycle: "h23",
      })
        .formatToParts(date)
        .map((p) => [p.type, p.value]),
    );
    const tokens: Record<string, string> = {
      yyyy: parts["year"],
      MM: parts["month"],
      dd: parts["day"],
      HH: parts["hour"],
      mm: parts["minute"],
      ss: parts["second"],
    };
    return format.replace(/yyyy|MM|dd|HH|mm|ss/g, (t) => tokens[t]);
  }
}
