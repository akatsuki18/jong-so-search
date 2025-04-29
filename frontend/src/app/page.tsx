'use client';

import { useState, useRef } from 'react';

export default function Home() {
  const [results, setResults] = useState<any[]>([]);
  const [loading, setLoading] = useState(false);
  const cacheRef = useRef<Map<string, any[]>>(new Map());

  const handleGetLocation = () => {
    navigator.geolocation.getCurrentPosition(
      async (position) => {
        const { latitude, longitude } = position.coords;

        const cacheKey = `${latitude.toFixed(4)},${longitude.toFixed(4)}`;

        // localStorageチェック
        const cached = localStorage.getItem(cacheKey);
        if (cached) {
          const parsed = JSON.parse(cached);
          const cacheAge = Date.now() - parsed.timestamp;
          const oneDay = 24 * 60 * 60 * 1000; // 24時間

          if (cacheAge < oneDay) {
            console.log('新しいキャッシュから取得:', cacheKey);
            setResults(parsed.data);
            return;
          } else {
            console.log('キャッシュ期限切れ、再取得します:', cacheKey);
            localStorage.removeItem(cacheKey); // 古いキャッシュは削除
          }
        }

        // メモリキャッシュチェック
        if (cacheRef.current.has(cacheKey)) {
          console.log('メモリキャッシュから取得:', cacheKey);
          setResults(cacheRef.current.get(cacheKey)!);
          return;
        }

        setLoading(true);

        try {
          const res = await fetch('http://localhost:8000/search', {
            method: 'POST',
            headers: {
              'Content-Type': 'application/json',
            },
            body: JSON.stringify({ latitude, longitude }),
          });
          const data = await res.json();
          const resultData = data.results || [];

          // キャッシュ保存
          cacheRef.current.set(cacheKey, resultData);
          const cacheItem = {
            timestamp: Date.now(), // 保存時間追加
            data: resultData,
          };
          localStorage.setItem(cacheKey, JSON.stringify(cacheItem));

          setResults(resultData);
        } catch (error) {
          console.error('検索エラー', error);
        } finally {
          setLoading(false);
        }
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
          disabled={loading}
        >
          {loading ? '検索中...' : '現在地から探す'}
        </button>
      </div>

      <div className="flex flex-col gap-6">
        {results.map((place, index) => {
          const googleMapsUrl = `https://www.google.com/maps/search/?api=1&query=${encodeURIComponent(place.name + ' ' + place.address)}`;

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

              <div className="flex items-center gap-2 text-sm mt-2">
                <span className="text-gray-800">⭐ {place.rating}（{place.user_ratings_total}件）</span>

                {/* ★ ここにおすすめマーク */}
                {place.positive_score >= 80 && (
                  <span className="ml-2 text-yellow-500 text-lg">🌟おすすめ</span>
                )}
              </div>

              {/* ★ ポジティブ・ネガティブスコア表示 */}
              {(place.positive_score !== null && place.negative_score !== null) && (
                <div className="text-gray-700 text-sm mt-2">
                  ポジティブ度: {place.positive_score}% / ネガティブ度: {place.negative_score}%
                </div>
              )}

              {/* 要約文 */}
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
