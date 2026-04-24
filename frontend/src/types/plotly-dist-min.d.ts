/**
 * Declaração mínima para `plotly.js-dist-min` (não tem @types oficial).
 * Usamos apenas para passar ao factory de react-plotly.js — não tipamos
 * a API completa do Plotly aqui (já vem de @types/plotly.js nos arquivos
 * que usam Plotly.Data, Plotly.Layout, etc.).
 */
declare module 'plotly.js-dist-min' {
  const Plotly: unknown
  export default Plotly
}
