import '../styles/globals.css'
import type { AppProps } from 'next/app'

export default function App({ Component, pageProps }: AppProps) {
  return (
    <>
      <style jsx global>{`
        * {
          box-sizing: border-box;
        }
        
        html, body {
          margin: 0;
          padding: 0;
          font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', 'Roboto', 'Oxygen',
            'Ubuntu', 'Cantarell', 'Fira Sans', 'Droid Sans', 'Helvetica Neue',
            sans-serif;
          -webkit-font-smoothing: antialiased;
          -moz-osx-font-smoothing: grayscale;
          background-color: #F7F8FA;
          color: #263238;
        }
        
        a {
          color: inherit;
          text-decoration: none;
        }
        
        button:focus {
          outline: 2px solid #2F5D8C;
          outline-offset: 2px;
        }
        
        input:focus,
        textarea:focus,
        select:focus {
          outline: 2px solid #2F5D8C;
          outline-offset: 2px;
        }
      `}</style>
      <Component {...pageProps} />
    </>
  )
}
