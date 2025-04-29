'use client';

import { useState } from 'react';
import useSWR from 'swr';

const fetcher = (url: string, body: any) =>
  fetch(url, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  }).then((res) => res.json());

export default function Home() {
  const [coords, setCoords] = useState<{ latitude: number; longitude: number } | null>(null);

  const { data, error, isLoading } = useSWR(
    coords ? ['/search', coords] : null,
    ([url, coords]) => fetcher('http://localhost:8000/search', coords),
    { revalidateOnFocus: false } // フォーカス時に再フェッチしない
  );

  const results = data?.results || [];

  const handleGetLocation = () => {
    navigator.geolocation.getCurrentPosition(
      (position) => {
        const { latitude, longitude } = position.coords;
        setCoords({ latitude, longitude });
      },
      (error) => console.error('位置情報エラー', error)
    );
  };

  return (
    <main className="bg-gray-50 min-h-screen p-6">
      <div className="max-w-2xl mx-auto">
        <h1 className="text-3xl font-bold text-gray-800 text-center mb-6">近くの雀荘を探す</h1>

        <div className="flex justify-center mb-8">
          <button
            onClick={handleGetLocation}
            disabled={isLoading}
            className="bg-blue-600 text-white font-semibold px-6 py-3 rounded-lg shadow-md hover:bg-blue-700 disabled:bg-blue-300 transition"
          >
            {isLoading ? '検索中...' : '現在地から探す'}
          </button>
        </div>

        <div className="space-y-6">
          {error && <p className="text-red-500">エラーが発生しました。</p>}
          {results.map((place, index) => {
            const googleMapsUrl = `https://www.google.com/maps/search/?api=1&query=${encodeURIComponent(place.name + ' ' + place.address)}`;

            const distanceKm = place.distanceKm ?? null;
            const walkMinutes = place.walkMinutes ?? null;
            const smokingStatus = place.smoking_status ?? place.smoking ?? null; // どちらも見ておく

            return (
              <div key={index} className="border-b border-gray-300 pb-6 mb-6">
                <a href={googleMapsUrl} target="_blank" rel="noopener noreferrer" className="text-xl font-bold text-blue-600 hover:underline">
                  {place.name}
                </a>

                <p className="text-sm text-gray-500 mt-1">{place.address}</p>

                {distanceKm !== null && (
                  <p className="text-sm text-gray-500 mt-2">
                    📍 現在地から {distanceKm.toFixed(1)} km
                    {walkMinutes && <>（徒歩{walkMinutes}分）</>}
                  </p>
                )}

                {smokingStatus && (
                  <div className="mt-3 inline-flex items-center gap-2 text-sm font-medium">
                    {smokingStatus === '禁煙' && <span className="px-2 py-1 bg-green-100 text-green-800 rounded-full">🚭 禁煙</span>}
                    {smokingStatus === '分煙' && <span className="px-2 py-1 bg-yellow-100 text-yellow-800 rounded-full">🚬 分煙</span>}
                    {smokingStatus === '喫煙可' && <span className="px-2 py-1 bg-red-100 text-red-600 rounded-full">🔥 喫煙可</span>}
                    {smokingStatus === '情報なし' && <span className="px-2 py-1 bg-gray-200 text-gray-600 rounded-full">❓ 情報なし</span>}
                  </div>
                )}

                <div className="flex items-center gap-2 mt-3 text-sm text-gray-700">
                  ⭐ {place.rating}（{place.user_ratings_total}件）
                  {place.positive_score >= 80 && (
                    <span className="ml-2 text-yellow-500">🌟おすすめ</span>
                  )}
                </div>

                {(place.positive_score !== null && place.negative_score !== null) && (
                  <div className="text-sm text-gray-500 mt-2">
                    ポジティブ度: {place.positive_score}% / ネガティブ度: {place.negative_score}%
                  </div>
                )}

                {place.summary && (
                  <p className="text-gray-700 text-sm mt-4 leading-relaxed">
                    {place.summary}
                  </p>
                )}
              </div>
            );
          })}
        </div>
      </div>
    </main>
  );
}
