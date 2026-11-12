import { Badge, Card, Evidence, Stat } from "../ui";

function Situation({ situation, title }) {
  return (
    <Card>
      <h3 className="font-bold">{title}</h3>
      <ul className="mt-2 space-y-1 text-sm text-zinc-300">
        {situation.facts.map((fact) => (
          <li key={fact}>{fact}</li>
        ))}
      </ul>
      {situation.flags.length > 0 && (
        <div className="mt-3 flex flex-wrap gap-1.5">
          {situation.flags.map((flag) => (
            <Badge key={flag} tone="orange">
              {flag}
            </Badge>
          ))}
        </div>
      )}
      {situation.evidence.map((note) => (
        <Evidence key={note}>{note}</Evidence>
      ))}
    </Card>
  );
}

export default function Conditions({ weather, situation }) {
  // Basketball is indoors: rest and travel only
  if (!weather) return <Situation situation={situation} title="Rest, travel & schedule" />;
  return (
    <div className="grid gap-3 lg:grid-cols-2">
      <Card>
        <h3 className="font-bold">Weather at kickoff</h3>
        {!weather.available ? (
          <p className="mt-2 text-sm text-zinc-400">{weather.reason}</p>
        ) : weather.indoor ? (
          <p className="mt-2 text-sm text-zinc-400">{weather.summary}</p>
        ) : (
          <div className="mt-3 grid grid-cols-3 gap-2">
            <Stat label="Temp" value={`${weather.temperature_f}°`} />
            <Stat label="Wind" value={`${weather.wind_mph} mph`} sub={`Gusts ${weather.gusts_mph}`} />
            <Stat label="Rain/snow" value={`${weather.precip_chance}%`} />
          </div>
        )}
        {weather.flags?.length > 0 && (
          <div className="mt-3 flex flex-wrap gap-1.5">
            {weather.flags.map((flag) => (
              <Badge key={flag} tone="yellow">
                {flag}
              </Badge>
            ))}
          </div>
        )}
        {weather.evidence?.map((note) => (
          <Evidence key={note}>{note}</Evidence>
        ))}
      </Card>

      <Situation situation={situation} title="Travel, rest & schedule" />
    </div>
  );
}