declare module '*.css';
declare module '*.csv?raw' { const content: string; export default content; }
