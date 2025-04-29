'use client';

import { useState } from 'react';
import useSWR from 'swr';

interface Place {
  name: string;
  address: string;
  distanceKm?: number;
  walkMinutes?: number;
  smoking_status?: string;
  smoking?: string;
  rating: number;
  user_ratings_total: number;
  positive_score?: number;
  negative_score?: number;
  summary?: string;
}

const fetcher = (url: string, body: any) =>
  fetch(url, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  }).then((res) => res.json());

const keywordFetcher = (url: string) =>
  fetch(url).then((res) => res.json());

export default function Home() {
  const [coords, setCoords] = useState<{ latitude: number; longitude: number } | null>(null);
  const [keyword, setKeyword] = useState<string>('');
  const [searchKeyword, setSearchKeyword] = useState<string>('');

  const { data: locationData, error: locationError, isLoading: locationIsLoading } = useSWR(
    coords ? ['/search', coords] : null,
    ([url, coords]) => fetcher('http://localhost:8000/search', coords),
    { revalidateOnFocus: false }
  );

  const { data: keywordData, error: keywordError, isLoading: keywordIsLoading } = useSWR(
    searchKeyword ? `http://localhost:8000/search_by_keyword?keyword=${encodeURIComponent(searchKeyword)}` : null,
    keywordFetcher,
    { revalidateOnFocus: false }
  );

  const results = searchKeyword ? (keywordData?.results || []) : (locationData?.results || []);

  const handleGetLocation = () => {
    navigator.geolocation.getCurrentPosition(
      (position) => {
        const { latitude, longitude } = position.coords;
        setCoords({ latitude, longitude });
        setSearchKeyword(''); // 位置情報検索時はキーワード検索をリセット
      },
      (error) => console.error('位置情報エラー', error)
    );
  };

  const handleKeywordSearch = (e: React.FormEvent) => {
    e.preventDefault();
    setSearchKeyword(keyword);
    setCoords(null); // キーワード検索時は位置情報をリセット
  };

  return (
    <main className="bg-gray-50 min-h-screen p-6">
      <div className="max-w-2xl mx-auto">
        <h1 className="text-3xl font-bold text-gray-800 text-center mb-6">雀荘を探す</h1>

        <div className="flex flex-col gap-4 mb-8">
          <form onSubmit={handleKeywordSearch} className="flex gap-2">
            <input
              type="text"
              value={keyword}
              onChange={(e) => setKeyword(e.target.value)}
              placeholder="店名や住所で検索"
              className="flex-1 px-4 py-2 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 text-gray-700"
            />
            <button
              type="submit"
              disabled={keywordIsLoading}
              className="bg-blue-600 text-white font-semibold px-6 py-2 rounded-lg shadow-md hover:bg-blue-700 disabled:bg-blue-300 transition"
            >
              {keywordIsLoading ? '検索中...' : '検索'}
            </button>
          </form>

          <div className="flex justify-center">
            <button
              onClick={handleGetLocation}
              disabled={locationIsLoading}
              className="bg-green-600 text-white font-semibold px-6 py-3 rounded-lg shadow-md hover:bg-green-700 disabled:bg-green-300 transition"
            >
              {locationIsLoading ? '検索中...' : '現在地から探す'}
            </button>
          </div>
        </div>

        <div className="space-y-6">
          {(locationError || keywordError) && <p className="text-red-500">エラーが発生しました。</p>}
          {results.map((place: Place, index: number) => {
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
                  {place.positive_score !== undefined && place.positive_score >= 80 && (
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
