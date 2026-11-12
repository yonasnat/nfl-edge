import { useLocation } from "react-router";

// Which league a page is about, from its address: /nba/... is NBA, everything else NFL
export function useSport() {
  const { pathname } = useLocation();
  return pathname === "/nba" || pathname.startsWith("/nba/") ? "nba" : "nfl";
}

export const SPORTS = {
  nfl: {
    name: "NFL",
    home: "/",
    methodology: "/methodology",
    api: "",
    homeLabel: "This week",
    since: "since 2015",
    dataSources:
      "Data: nflverse (play-by-play, schedules, official injury reports), ESPN (injury statuses and news), Open-Meteo (weather).",
  },
  nba: {
    name: "NBA",
    home: "/nba",
    methodology: "/nba/methodology",
    api: "/nba",
    homeLabel: "Today",
    since: "since 2022-23",
    dataSources: "Data: ESPN box scores via sportsdataverse, ESPN (injury statuses, news, live lines).",
  },
};

export function gamePath(sport, gameId) {
  return sport === "nba" ? `/nba/game/${gameId}` : `/game/${gameId}`;
}
