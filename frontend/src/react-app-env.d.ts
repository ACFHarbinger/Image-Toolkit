/// <reference types="react-scripts" />

declare module '*.css' {
  const classes: { readonly [key: string]: string };
  export default classes;
}

declare namespace NodeJS {
  interface Timeout {}
}

