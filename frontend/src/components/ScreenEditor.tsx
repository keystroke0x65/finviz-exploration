import { FormEvent, useState } from "react";
import {
  FormFieldName,
  FormFields,
  MarketCapOption,
  parseScreenerUrl,
  ScreenDraft,
  ScreenForm,
  ScreenInput,
} from "../api/screens";

export type ScreenEditorInitial = ScreenDraft & { name: string; feeds_watchlist: boolean };

interface ScreenEditorProps {
  initial: ScreenEditorInitial | null;
  formFields: FormFields;
  onSave: (input: ScreenInput) => Promise<void>;
  onCancel: () => void;
}

const FIELD_LABELS: Record<FormFieldName, string> = {
  country: "Country",
  price_under: "Price under ($)",
  float_under_millions: "Float under (M)",
  market_cap: "Market cap",
  volume_over_thousands: "Volume over (K)",
  relative_volume_over: "Relative volume over",
};

const TEXT_FIELDS: FormFieldName[] = ["country", "market_cap"];

const OPTION_LABELS: Record<string, string> = {
  usa: "USA",
  large_and_under: "Under $200B",
  mid_and_under: "Under $10B",
  small_and_under: "Under $2B",
  micro_and_under: "Under $300M",
  nano: "Under $50M",
};

const FIELD_ORDER = Object.keys(FIELD_LABELS) as FormFieldName[];

type FieldValues = Record<FormFieldName, string>;

function toFieldValues(form: ScreenForm): FieldValues {
  const values = {} as FieldValues;
  for (const field of FIELD_ORDER) {
    const value = form[field];
    values[field] = value == null ? "" : String(value);
  }
  return values;
}

function toScreenForm(values: FieldValues): ScreenForm {
  const textValue = (field: FormFieldName) => values[field] || null;
  const numberValue = (field: FormFieldName) => (values[field] ? Number(values[field]) : null);
  return {
    country: textValue("country") as ScreenForm["country"],
    price_under: numberValue("price_under"),
    float_under_millions: numberValue("float_under_millions"),
    market_cap: textValue("market_cap") as MarketCapOption | null,
    volume_over_thousands: numberValue("volume_over_thousands"),
    relative_volume_over: numberValue("relative_volume_over"),
  };
}

function errorMessage(error: unknown): string {
  return error instanceof Error ? error.message : "Unknown error";
}

export function ScreenEditor({ initial, formFields, onSave, onCancel }: ScreenEditorProps) {
  const [name, setName] = useState(initial?.name ?? "");
  const [fieldValues, setFieldValues] = useState<FieldValues>(toFieldValues(initial?.form ?? {}));
  const [signal, setSignal] = useState(initial?.signal ?? "");
  const [order, setOrder] = useState<string | null>(initial?.order ?? null);
  const [extraFilters, setExtraFilters] = useState<string[]>(initial?.extra_filters ?? []);
  const [feedsWatchlist, setFeedsWatchlist] = useState(initial?.feeds_watchlist ?? false);
  const [screenerUrl, setScreenerUrl] = useState("");
  const [error, setError] = useState<string | null>(null);

  async function handleImport() {
    setError(null);
    try {
      const draft = await parseScreenerUrl(screenerUrl);
      setFieldValues(toFieldValues(draft.form));
      setSignal(draft.signal ?? "");
      setOrder(draft.order);
      setExtraFilters(draft.extra_filters);
    } catch (importError) {
      setError(errorMessage(importError));
    }
  }

  async function handleSubmit(event: FormEvent) {
    event.preventDefault();
    setError(null);
    try {
      await onSave({
        name,
        form: toScreenForm(fieldValues),
        extra_filters: extraFilters,
        signal: signal || null,
        order,
        feeds_watchlist: feedsWatchlist,
      });
    } catch (saveError) {
      setError(errorMessage(saveError));
    }
  }

  return (
    <form onSubmit={handleSubmit}>
      <fieldset>
        <legend>Import from Finviz</legend>
        <label>
          Finviz screener URL
          {/* Plain text, not type="url": the box sits inside the save form, and an
              invalid URL left in it must not block saving the rest. The backend
              validates the URL on import. */}
          <input
            type="text"
            inputMode="url"
            value={screenerUrl}
            onChange={(event) => setScreenerUrl(event.target.value)}
            placeholder="https://finviz.com/screener.ashx?v=111&f=..."
          />
        </label>
        <button type="button" onClick={handleImport}>
          Import
        </button>
      </fieldset>

      <label>
        Name
        <input type="text" value={name} onChange={(event) => setName(event.target.value)} />
      </label>

      {FIELD_ORDER.map((field) => (
        <label key={field}>
          {FIELD_LABELS[field]}
          <select
            value={fieldValues[field]}
            onChange={(event) => setFieldValues({ ...fieldValues, [field]: event.target.value })}
          >
            <option value="">Any</option>
            {formFields.options[field].map((option) => (
              <option key={option} value={String(option)}>
                {TEXT_FIELDS.includes(field) ? OPTION_LABELS[option] ?? option : option}
              </option>
            ))}
          </select>
        </label>
      ))}

      <label>
        Signal
        <select value={signal} onChange={(event) => setSignal(event.target.value)}>
          <option value="">None</option>
          {/* A pasted signal the form doesn't offer is kept and shown as its raw
              code; otherwise the select would silently display "None". */}
          {signal && !(signal in formFields.signals) && <option value={signal}>{signal}</option>}
          {Object.entries(formFields.signals).map(([code, label]) => (
            <option key={code} value={code}>
              {label}
            </option>
          ))}
        </select>
      </label>

      {order && <p>Sorted by: {order}</p>}

      {extraFilters.length > 0 && (
        <div>
          <p>Other Finviz filters</p>
          <ul>
            {extraFilters.map((code) => (
              <li key={code}>
                {code}{" "}
                <button
                  type="button"
                  aria-label={`Remove ${code}`}
                  onClick={() => setExtraFilters(extraFilters.filter((existing) => existing !== code))}
                >
                  ×
                </button>
              </li>
            ))}
          </ul>
        </div>
      )}

      <label>
        <input
          type="checkbox"
          checked={feedsWatchlist}
          onChange={(event) => setFeedsWatchlist(event.target.checked)}
        />
        Feeds watchlist
      </label>

      {error && <p role="alert">{error}</p>}

      <button type="submit">Save</button>
      <button type="button" onClick={onCancel}>
        Cancel
      </button>
    </form>
  );
}
