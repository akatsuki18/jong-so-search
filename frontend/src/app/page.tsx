'use client';

import { useState } from 'react';
import useSWR from 'swr';

// fetcher関数を定義
const fetcher = async (url: string, location: { latitude: number; longitude: number }) => {
  const res = await fetch(url, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(location),
  });
  const data = await res.json();
  return data.results || [];
};

// 距離計算
const calculateDistance = (lat1: number, lon1: number, lat2: number, lon2: number) => {
  const R = 6371; // km
  const dLat = (lat2 - lat1) * Math.PI / 180;
  const dLon = (lon2 - lon1) * Math.PI / 180;
  const a =
    Math.sin(dLat / 2) ** 2 +
    Math.cos(lat1 * Math.PI / 180) * Math.cos(lat2 * Math.PI / 180) *
    Math.sin(dLon / 2) ** 2;
  const c = 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1 - a));
  return R * c;
};

export default function Home() {
  const [location, setLocation] = useState<{ latitude: number; longitude: number } | null>(null);

  const { data: results, error, isLoading } = useSWR(
    location ? ['http://localhost:8000/search', location] : null,
    ([url, loc]) => fetcher(url, loc)
  );

  const handleGetLocation = () => {
    navigator.geolocation.getCurrentPosition(
      (position) => {
        const { latitude, longitude } = position.coords;
        setLocation({ latitude, longitude });
      },
      (error) => {
        console.error('位置情報エラー', error);
      }
    );
  };

  return (
    <main className="p-4 max-w-md mx-auto">
      <h1 className="text-2xl font-bold mb-4 text-center">近くの雀荘を探す</h1>

      <div className="flex justify-center mb-6">
        <button
          onClick={handleGetLocation}
          className="bg-blue-500 text-white px-6 py-2 rounded-lg hover:bg-blue-600 disabled:bg-blue-300"
          disabled={isLoading}
        >
          {isLoading ? '検索中...' : '現在地から探す'}
        </button>
      </div>

      {error && (
        <p className="text-red-500 text-center mb-4">エラーが発生しました！再試行してください。</p>
      )}

      <div className="flex flex-col gap-6">
        {results && results.map((place: any, index: number) => {
          const googleMapsUrl = `https://www.google.com/maps/search/?api=1&query=${encodeURIComponent(place.name + ' ' + place.address)}`;

          // 距離・徒歩分数計算
          const distance = location && place.lat && place.lng
            ? calculateDistance(location.latitude, location.longitude, place.lat, place.lng)
            : null;
          const walkingMinutes = distance ? Math.round(distance * 60 / 4) : null;

          return (
            <div key={index} className="p-4 bg-white border border-gray-200 rounded-2xl shadow-md">
              <a
                href={googleMapsUrl}
                target="_blank"
                rel="noopener noreferrer"
                className="text-xl font-bold text-blue-600 hover:underline"
              >
                {place.name}
              </a>

              <p className="text-gray-600 text-sm mt-1">{place.address}</p>

              {/* 距離と徒歩分数 */}
              {distance !== null && (
                <p className="text-gray-600 text-sm mt-1">
                  📍 現在地から {distance.toFixed(1)} km
                  {walkingMinutes !== null && `（徒歩${walkingMinutes}分）`}
                </p>
              )}

              {/* 星評価 */}
              <div className="flex items-center gap-2 text-sm mt-2">
                <span className="text-gray-800">⭐ {place.rating}（{place.user_ratings_total}件）</span>

                {/* おすすめマーク */}
                {place.positive_score >= 80 && (
                  <span className="ml-2 text-yellow-500 text-lg">🌟おすすめ</span>
                )}
              </div>

              {/* ポジティブ・ネガティブスコア */}
              {(place.positive_score !== null && place.negative_score !== null) && (
                <div className="text-gray-700 text-sm mt-2">
                  ポジティブ度: {place.positive_score}% / ネガティブ度: {place.negative_score}%
                </div>
              )}

              {/* 要約 */}
              {place.summary && (
                <p className="text-gray-800 text-sm mt-3">{place.summary}</p>
              )}
            </div>
          );
        })}
      </div>
    </main>
  );
}
