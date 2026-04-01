declare module 'prism-media' {
  import { Transform } from 'stream';

  namespace opus {
    class Decoder extends Transform {
      constructor(options: { rate: number; channels: number; frameSize: number });
    }
  }

  export { opus };
}
