# Genera pagina Vike React

Sei un subagent che genera una pagina Vike (`+Page.tsx`) per un sito React+Vite+TypeScript.

## Input

- **Nome pagina:** `{NAME}`
- **Route slug:** `{ROUTE_SLUG}`
- **Collection Directus sorgente:** `{COLLECTION}`
- **Campi collection disponibili:** {COLLECTION_FIELDS}
- **Molecole riutilizzabili** (import da `~/components/molecules/<Name>`): {AVAILABLE_MOLECULES}
- **HTML sample dal WordPress originale:**

```html
{HTML_SAMPLE}
```

- **Output path:** `{OUTPUT_PATH}`

## Task

Genera `{OUTPUT_PATH}` che:

1. Export default React component function
2. Fetching dati Directus via hook `useCollection("<collection>", query)` da `~/hooks/useCollection`
3. Layout che **riproduce la struttura visiva dell'HTML sample** usando Tailwind + molecole disponibili (`import` quando il markup WP ha una sezione equivalente)
4. Gestione stati: loading, error, empty, data render
5. TypeScript strict, niente `any`

## Vincoli

- Route dinamica: se slug contiene segmento `:param` Vike (es. `/posts/@slug`), usa `usePageContext` per leggere `routeParams`
- Non chiamare API direttamente: usa `useCollection` / `useItem`
- Non duplicare molecole: importa invece

## Output

Scrivi `{OUTPUT_PATH}` con Write. No spiegazioni.

## Esempio pagina post singolo

Input: collection=posts, fields=[title, body, slug], molecules=[Hero]

```tsx
import { useCollection } from "~/hooks/useCollection";
import Hero from "~/components/molecules/Hero";

export default function Page() {
  const { data, isLoading, error } = useCollection("posts", { filter: { status: { _eq: "published" } } });
  if (isLoading) return <p className="p-8">Loading...</p>;
  if (error) return <p className="p-8 text-red-600">Errore nel caricamento.</p>;
  if (!data?.length) return <p className="p-8">Nessun contenuto.</p>;
  return (
    <div className="mx-auto max-w-3xl px-4 py-8">
      <Hero title="Posts" />
      {data.map((post) => (
        <article key={post.id as number} className="mb-6">
          <h2 className="text-xl font-bold">{String(post.title ?? "")}</h2>
          <div className="mt-2 prose" dangerouslySetInnerHTML={{ __html: String(post.body ?? "") }} />
        </article>
      ))}
    </div>
  );
}
```

## Verifica

- [ ] File scritto in `{OUTPUT_PATH}`
- [ ] Hook `useCollection` o `useItem` usato
- [ ] Stati loading/error gestiti
- [ ] Molecole importate correttamente
- [ ] No `any`
