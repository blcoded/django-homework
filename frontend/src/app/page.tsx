export default function HomePage() {
  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold tracking-tight">Home Dashboard</h1>
        <p className="text-sm text-muted-foreground">
          Welcome to your household chore hub.
        </p>
      </div>
      <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-4">
        <div className="rounded-xl border bg-card p-6 shadow-sm">
          <h3 className="text-sm font-medium text-muted-foreground">My Active Chores</h3>
          <p className="mt-2 text-3xl font-bold">2</p>
        </div>
        <div className="rounded-xl border bg-card p-6 shadow-sm">
          <h3 className="text-sm font-medium text-muted-foreground">Next Up</h3>
          <p className="mt-2 text-3xl font-bold">1</p>
        </div>
        <div className="rounded-xl border bg-card p-6 shadow-sm">
          <h3 className="text-sm font-medium text-muted-foreground">Current Streak</h3>
          <p className="mt-2 text-3xl font-bold">5 🔥</p>
        </div>
        <div className="rounded-xl border bg-card p-6 shadow-sm">
          <h3 className="text-sm font-medium text-muted-foreground">Household Completion</h3>
          <p className="mt-2 text-3xl font-bold">94%</p>
        </div>
      </div>
    </div>
  );
}
