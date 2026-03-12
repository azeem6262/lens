import { NextResponse } from 'next/server';

export async function GET(request: Request) {
  const { searchParams } = new URL(request.url);

  const match_id = searchParams.get('match_id');
  const team = searchParams.get('team');
  const half = searchParams.get('half'); 

  if (!match_id || !team || !half) {
    return NextResponse.json(
      { error: "Missing required query parameters" },
      { status: 400 }
    );
  }

  const res = await fetch(
    `http://localhost:8000/pass-network?match_id=${match_id}&team=${team}&half=${half}`
  );

  const data = await res.json();

  return NextResponse.json(data);
}
