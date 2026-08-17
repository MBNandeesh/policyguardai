import Head from 'next/head'

export default function Home() {
  return (
    <div className="min-h-screen bg-gray-50">
      <Head>
        <title>PolicyGuard AI</title>
        <meta name="description" content="PolicyGuard AI - Officer Copilot" />
      </Head>

      <main className="max-w-4xl mx-auto p-8">
        <header className="mb-8">
          <h1 className="text-3xl font-semibold">PolicyGuard AI</h1>
          <p className="text-sm text-gray-600">Officer Copilot for tender & contract compliance</p>
        </header>

        <section className="bg-white shadow rounded p-6">
          <h2 className="text-xl font-medium mb-2">Dashboard (shell)</h2>
          <p className="text-gray-700">This is a placeholder dashboard shell. Connect backend to view health and documents.</p>
        </section>
      </main>
    </div>
  )
}
