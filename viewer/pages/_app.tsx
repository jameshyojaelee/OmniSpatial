import type { AppProps } from "next/app";
import Head from "next/head";

import "../styles/globals.css";

export default function OmniSpatialApp({ Component, pageProps }: AppProps): JSX.Element {
  return (
    <>
      <Head>
        <title>OmniSpatial Viewer</title>
        <meta name="viewport" content="initial-scale=1, width=device-width" />
      </Head>
      <Component {...pageProps} />
    </>
  );
}
