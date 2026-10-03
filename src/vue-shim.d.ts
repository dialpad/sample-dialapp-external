// ESLint's type-aware rules read .vue imports through TypeScript, which doesn't understand them.
// vue-tsc ignores this and checks the real components.
declare module '*.vue' {
  import type { DefineComponent } from 'vue';

  const component: DefineComponent<object, object, unknown>;
  export default component;
}
