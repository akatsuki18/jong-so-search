'use client';

import { useState, useEffect } from 'react';
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
  id?: string;
}

// APIのベースURL（ローカル開発用）
const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

const fetcher = async (url: string, body: any) => {
  console.log(`Fetcher calling: ${url}`);
  let res;
  try {
    res = await fetch(url, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    });

    console.log(`Fetcher response status: ${res.status} for ${url}`);

    const resClone = res.clone();
    const rawText = await resClone.text();
    console.log(`Fetcher raw response text for ${url}: [${rawText}]`);

    if (!res.ok) {
      console.error(`Fetcher error response text: ${rawText}`);
      throw new Error(`An error occurred while fetching the data. Status: ${res.status}, Body: ${rawText}`);
    }

    console.log(`Attempting to parse JSON for ${url}...`);
    const data = await res.json();
    console.log(`Successfully parsed JSON for ${url}. Type: ${typeof data}`);
    console.log(`Fetcher response JSON data for ${url}:`, data);

    if (data === null) {
        console.warn(`Parsed JSON data is null for ${url}. Raw text was: [${rawText}]`);
    }

    // SWRに返す直前の値をログ
    console.log(`Fetcher returning data for ${url}:`, data);
    return data;
  } catch (error: any) {
    console.error(`Fetcher caught an error for ${url}:`, error);
    if (error instanceof Error) {
        console.error('Error name:', error.name);
        console.error('Error message:', error.message);
        console.error('Error stack:', error.stack);
    } else {
        console.error('Caught non-Error object:', error);
    }
    if(res) {
      console.error(`Response status at time of error: ${res.status}`);
    }
    // エラー時はnullではなくエラーをスローしてSWRにエラーを伝える
    throw error;
  }
};

const keywordFetcher = async (url: string) => {
  console.log(`KeywordFetcher calling: ${url}`);
  let res;
  try {
    res = await fetch(url);
    console.log(`KeywordFetcher response status: ${res.status} for ${url}`);

    const resClone = res.clone();
    const rawText = await resClone.text();
    console.log(`KeywordFetcher raw response text for ${url}: [${rawText}]`);

    if (!res.ok) {
      console.error(`KeywordFetcher error response text: ${rawText}`);
      throw new Error(`An error occurred while fetching the keyword data. Status: ${res.status}, Body: ${rawText}`);
    }

    console.log(`Attempting to parse JSON for ${url}...`);
    const data = await res.json();
    console.log(`Successfully parsed JSON for ${url}. Type: ${typeof data}`);
    console.log(`KeywordFetcher response JSON data for ${url}:`, data);

    if (data === null) {
      console.warn(`Parsed JSON data is null for ${url}. Raw text was: [${rawText}]`);
    }

    console.log(`KeywordFetcher returning data for ${url}:`, data);
    return data;
  } catch (error: any) {
    console.error(`KeywordFetcher caught an error for ${url}:`, error);
    if (error instanceof Error) {
      console.error('Error name:', error.name);
      console.error('Error message:', error.message);
      console.error('Error stack:', error.stack);
    } else {
      console.error('Caught non-Error object:', error);
    }
    if(res) {
      console.error(`Response status at time of error: ${res.status}`);
    }
    throw error;
  }
};

export default function Home() {
  const [coords, setCoords] = useState<{ latitude: number; longitude: number } | null>(null);
  const [keyword, setKeyword] = useState<string>('');
  const [searchKeyword, setSearchKeyword] = useState<string>('');

  const { data: locationData, error: locationError, isLoading: locationIsLoading } = useSWR(
    coords ? ['/api/search', coords] : null,
    ([url, coords]) => fetcher(`${API_BASE_URL}${url}`, coords),
    {
      revalidateOnFocus: false,
      // エラー時に再試行しないように設定 (デバッグのため)
      shouldRetryOnError: false
    }
  );

  const { data: keywordData, error: keywordError, isLoading: keywordIsLoading } = useSWR(
    searchKeyword ? `/api/search_by_keyword?keyword=${encodeURIComponent(searchKeyword)}` : null,
    (url) => keywordFetcher(`${API_BASE_URL}${url}`),
    {
      revalidateOnFocus: false,
      shouldRetryOnError: false
    }
  );

  // ログ出力用のuseEffect
  useEffect(() => {
    // SWR データが undefined から始まるため、nullと比較する
    if (locationData !== undefined) {
      console.log("SWR Location Data Updated:", locationData);
    }
    if(locationError) console.error("SWR Location Error:", locationError);
  }, [locationData, locationError]);

  useEffect(() => {
    if (keywordData !== undefined) {
      console.log("SWR Keyword Data Updated:", keywordData);
    }
    if(keywordError) console.error("SWR Keyword Error:", keywordError);
  }, [keywordData, keywordError]);

  const results: Place[] = searchKeyword ? (keywordData?.results || []) : (locationData?.results || []);

  // 算出された results のログ
  useEffect(() => {
    console.log("Calculated Results:", results);
    console.log("Results length:", results.length);
  }, [results]);

  const handleGetLocation = () => {
    navigator.geolocation.getCurrentPosition(
      (position) => {
        const { latitude, longitude } = position.coords;
        console.log(`位置情報を取得しました: 緯度 ${latitude}, 経度 ${longitude}`);
        setCoords({ latitude, longitude });
        setSearchKeyword('');
      },
      (error) => console.error('位置情報エラー', error)
    );
  };

  const handleKeywordSearch = (e: React.FormEvent) => {
    e.preventDefault();
    setSearchKeyword(keyword);
    setCoords(null);
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
          {(locationIsLoading || keywordIsLoading) && <p className="text-gray-500 text-center">検索中...</p>}
          {!(locationIsLoading || keywordIsLoading) && (locationError || keywordError) && <p className="text-red-500">エラーが発生しました: {locationError?.message || keywordError?.message}</p>}
          {!(locationIsLoading || keywordIsLoading) && !(locationError || keywordError) && results.length === 0 && <p className="text-gray-500 text-center">検索結果がありません。</p>}
          {results.map((place: Place, index: number) => {
            const key = place.id || index;
            const googleMapsUrl = `https://www.google.com/maps/search/?api=1&query=${encodeURIComponent(place.name + ' ' + place.address)}`;

            const distanceKm = place.distanceKm ?? null;
            const walkMinutes = place.walkMinutes ?? null;
            const smokingStatus = place.smoking_status ?? place.smoking ?? null;

            return (
              <div key={key} className="border-b border-gray-300 pb-6 mb-6">
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
