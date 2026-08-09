# Function: autocorrelation()

> **autocorrelation**(`signal`): `number`[]

Defined in: [signal.ts:104](https://github.com/ACFHarbinger/Image-Toolkit/blob/9190541af071250910b565c74fabdf538a60aa6c/frontend/src/math/signal.ts#L104)

Circular autocorrelation via FFT.

 Returns the autocorrelation at lags [0 .. N-1].  The DC component at lag 0
 is the signal energy.  Used for detecting ghosting (Phase 3.8A).

## Parameters

### signal

`number`[]

## Returns

`number`[]
