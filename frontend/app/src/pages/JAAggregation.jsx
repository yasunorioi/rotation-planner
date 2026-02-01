/**
 * JA集計ページ (管理者用)
 */

import { useEffect, useState } from 'react';
import { jaApi } from '../lib/api';
import { useAuthStore } from '../store/authStore';

export default function JAAggregation() {
  const { user } = useAuthStore();
  const [farmers, setFarmers] = useState([]);
  const [selectedFarmer, setSelectedFarmer] = useState(null);
  const [farmerFields, setFarmerFields] = useState([]);
  const [farmerPlans, setFarmerPlans] = useState([]);
  const [pesticideAggregation, setPesticideAggregation] = useState([]);
  const [selectedYear, setSelectedYear] = useState(new Date().getFullYear());
  const [activeTab, setActiveTab] = useState('farmers');
  const [isLoading, setIsLoading] = useState(true);

  const years = Array.from({ length: 5 }, (_, i) => new Date().getFullYear() - 2 + i);

  useEffect(() => {
    if (user?.role === 'admin') {
      loadFarmers();
    }
  }, [user]);

  useEffect(() => {
    if (activeTab === 'pesticides') {
      loadPesticideAggregation();
    }
  }, [selectedYear, activeTab]);

  const loadFarmers = async () => {
    setIsLoading(true);
    try {
      const data = await jaApi.listFarmers();
      setFarmers(data);
    } catch (err) {
      console.error('Failed to load farmers:', err);
    } finally {
      setIsLoading(false);
    }
  };

  const loadFarmerDetails = async (farmerId) => {
    try {
      const [fields, plans] = await Promise.all([
        jaApi.getFarmerFields(farmerId),
        jaApi.getFarmerPlans(farmerId),
      ]);
      setFarmerFields(fields);
      setFarmerPlans(plans);
      setSelectedFarmer(farmers.find((f) => f.username === farmerId));
    } catch (err) {
      console.error('Failed to load farmer details:', err);
    }
  };

  const loadPesticideAggregation = async () => {
    setIsLoading(true);
    try {
      const data = await jaApi.aggregatePesticideOrders(selectedYear);
      setPesticideAggregation(data);
    } catch (err) {
      console.error('Failed to load aggregation:', err);
    } finally {
      setIsLoading(false);
    }
  };

  if (user?.role !== 'admin') {
    return (
      <div className="ja-aggregation-page">
        <div className="access-denied">
          <h1>⛔ アクセス権限がありません</h1>
          <p>このページは管理者のみ閲覧できます。</p>
        </div>
      </div>
    );
  }

  return (
    <div className="ja-aggregation-page">
      <div className="page-header">
        <h1>🏛️ JA集計</h1>
        <div className="tab-buttons">
          <button
            className={`tab-btn ${activeTab === 'farmers' ? 'active' : ''}`}
            onClick={() => setActiveTab('farmers')}
          >
            農家一覧
          </button>
          <button
            className={`tab-btn ${activeTab === 'pesticides' ? 'active' : ''}`}
            onClick={() => setActiveTab('pesticides')}
          >
            農薬発注集計
          </button>
        </div>
      </div>

      {activeTab === 'farmers' && (
        <div className="farmers-section">
          {selectedFarmer ? (
            <div className="farmer-details">
              <button onClick={() => setSelectedFarmer(null)} className="btn-back">
                ← 一覧に戻る
              </button>
              <h2>{selectedFarmer.display_name || selectedFarmer.username} さんの情報</h2>

              <div className="detail-section">
                <h3>🗺️ ほ場一覧 ({farmerFields.length}件)</h3>
                {farmerFields.length === 0 ? (
                  <p className="empty-message">ほ場が登録されていません</p>
                ) : (
                  <table className="data-table">
                    <thead>
                      <tr>
                        <th>コード</th>
                        <th>名前</th>
                        <th>地区</th>
                        <th>面積(ha)</th>
                      </tr>
                    </thead>
                    <tbody>
                      {farmerFields.map((f) => (
                        <tr key={f.id}>
                          <td>{f.field_code}</td>
                          <td>{f.field_name || '-'}</td>
                          <td>{f.district || '-'}</td>
                          <td>{f.area_ha.toFixed(2)}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                )}
              </div>

              <div className="detail-section">
                <h3>📊 輪作計画 ({farmerPlans.length}件)</h3>
                {farmerPlans.length === 0 ? (
                  <p className="empty-message">計画が登録されていません</p>
                ) : (
                  <table className="data-table">
                    <thead>
                      <tr>
                        <th>計画名</th>
                        <th>開始年</th>
                        <th>年数</th>
                        <th>作成日</th>
                      </tr>
                    </thead>
                    <tbody>
                      {farmerPlans.map((p) => (
                        <tr key={p.id}>
                          <td>{p.name}</td>
                          <td>{p.start_year}年</td>
                          <td>{p.years}年</td>
                          <td>{new Date(p.created_at).toLocaleDateString()}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                )}
              </div>
            </div>
          ) : (
            <>
              {isLoading ? (
                <p>読み込み中...</p>
              ) : farmers.length === 0 ? (
                <p className="empty-message">農家が登録されていません</p>
              ) : (
                <table className="data-table">
                  <thead>
                    <tr>
                      <th>ユーザー名</th>
                      <th>表示名</th>
                      <th>役割</th>
                      <th>操作</th>
                    </tr>
                  </thead>
                  <tbody>
                    {farmers.map((farmer) => (
                      <tr key={farmer.username}>
                        <td>{farmer.username}</td>
                        <td>{farmer.display_name || '-'}</td>
                        <td>{farmer.role === 'admin' ? '管理者' : '農家'}</td>
                        <td>
                          <button
                            onClick={() => loadFarmerDetails(farmer.username)}
                            className="btn-secondary btn-sm"
                          >
                            詳細
                          </button>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              )}
            </>
          )}
        </div>
      )}

      {activeTab === 'pesticides' && (
        <div className="pesticides-section">
          <div className="filter-row">
            <select
              value={selectedYear}
              onChange={(e) => setSelectedYear(parseInt(e.target.value))}
              className="year-select"
            >
              {years.map((y) => (
                <option key={y} value={y}>{y}年</option>
              ))}
            </select>
          </div>

          {isLoading ? (
            <p>読み込み中...</p>
          ) : pesticideAggregation.length === 0 ? (
            <p className="empty-message">{selectedYear}年の発注データがありません</p>
          ) : (
            <table className="data-table">
              <thead>
                <tr>
                  <th>農薬名</th>
                  <th>合計数量</th>
                  <th>単位</th>
                  <th>発注者数</th>
                </tr>
              </thead>
              <tbody>
                {pesticideAggregation.map((item, idx) => (
                  <tr key={idx}>
                    <td>{item.pesticide_name}</td>
                    <td>{item.total_quantity}</td>
                    <td>{item.unit}</td>
                    <td>{item.order_count}人</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
      )}
    </div>
  );
}
