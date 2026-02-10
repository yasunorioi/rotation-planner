/**
 * ダッシュボード
 */

import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { useAuthStore } from '../store/authStore';
import { dashboardApi, planApi } from '../lib/api';
import { Spinner } from '../components/Loading';

export default function Dashboard() {
  const { user } = useAuthStore();
  const [stats, setStats] = useState(null);
  const [isLoading, setIsLoading] = useState(true);
  const [currentYearPlan, setCurrentYearPlan] = useState(null); // 今年度の計画データ

  const currentYear = new Date().getFullYear();

  useEffect(() => {
    const loadData = async () => {
      try {
        // 統計情報を取得
        const statsData = await dashboardApi.getStats();
        setStats(statsData);

        // 最新の輪作計画を取得し、今年度の作付予定を抽出
        const plans = await planApi.list();
        if (plans && plans.length > 0) {
          // 今年度を含む計画を検索
          for (const planSummary of plans) {
            if (planSummary.start_year <= currentYear && planSummary.end_year >= currentYear) {
              const plan = await planApi.get(planSummary.id);
              if (plan && plan.details) {
                // 今年度の詳細を抽出
                const currentYearDetails = plan.details.filter(d => d.year === currentYear);
                if (currentYearDetails.length > 0) {
                  setCurrentYearPlan({
                    id: plan.id,
                    name: plan.name,
                    details: currentYearDetails,
                  });
                  break;
                }
              }
            }
          }
        }
      } catch (err) {
        console.error('データの取得に失敗しました', err);
      } finally {
        setIsLoading(false);
      }
    };
    loadData();
  }, [currentYear]);

  return (
    <div className="dashboard">
      <h1>ダッシュボード</h1>
      <p className="welcome">ようこそ、{user?.display_name || user?.username} さん</p>

      {/* ワークフロー説明 */}
      <div className="workflow-section">
        <h2>📋 ワークフロー</h2>
        <div className="workflow-steps">
          <div className="workflow-step">
            <span className="step-number">1</span>
            <span className="step-icon">🗺️</span>
            <span className="step-text">ほ場登録</span>
            <span className="step-desc">地図上でほ場を登録</span>
          </div>
          <span className="workflow-arrow">→</span>
          <div className="workflow-step">
            <span className="step-number">2</span>
            <span className="step-icon">🌾</span>
            <span className="step-text">輪作計画</span>
            <span className="step-desc">過去データから最適な計画を生成</span>
          </div>
          <span className="workflow-arrow">→</span>
          <div className="workflow-step">
            <span className="step-number">3</span>
            <span className="step-icon">💊</span>
            <span className="step-text">農薬発注</span>
            <span className="step-desc">輪作計画から必要量を算出</span>
          </div>
        </div>
      </div>

      {/* 統計カード */}
      <div className="stats-grid">
        <div className="stat-card">
          <div className="stat-value">{stats?.fields?.count ?? '-'}</div>
          <div className="stat-label">登録ほ場数</div>
        </div>
        <div className="stat-card">
          <div className="stat-value">{stats?.fields?.total_area_ha?.toFixed(1) ?? '-'} ha</div>
          <div className="stat-label">総面積</div>
        </div>
        <div className="stat-card">
          <div className="stat-value">{stats?.plans?.count ?? '-'}</div>
          <div className="stat-label">輪作計画</div>
        </div>
        <div className="stat-card">
          <div className="stat-value">{stats?.orders?.total ?? '-'}</div>
          <div className="stat-label">農薬発注</div>
        </div>
        <div className="stat-card">
          <div className="stat-value">{stats?.records?.this_month ?? '-'}</div>
          <div className="stat-label">今月の防除記録</div>
        </div>
      </div>

      {/* 今年度の計画（輪作計画連携） */}
      <div className="plan-section">
        <h2>📅 {currentYear}年の作付計画</h2>
        {currentYearPlan ? (
          <>
            <p className="plan-name">
              計画名: <Link to={`/plans`}>{currentYearPlan.name}</Link>
            </p>
            <div className="plan-grid">
              {currentYearPlan.details.map((detail) => (
                <div key={`${detail.field_id}-${detail.year}`} className="plan-item">
                  <span className="plan-field">{detail.field_name || detail.field_code}</span>
                  <span className="plan-crop">{detail.crop}</span>
                </div>
              ))}
            </div>
          </>
        ) : (
          <div className="no-plan">
            <p>今年度の輪作計画がありません</p>
            <Link to="/rotation" className="btn btn-primary">計画を作成する</Link>
          </div>
        )}
      </div>

      {/* 今年度の作付状況 */}
      {stats?.crops && stats.crops.length > 0 && (
        <div className="crops-section">
          <h2>🌱 今年度の作付状況</h2>
          <div className="crops-grid">
            {stats.crops.map((crop) => (
              <div key={crop.name} className="crop-item">
                <span className="crop-name">{crop.name}</span>
                <span className="crop-area">{crop.area_ha.toFixed(1)} ha</span>
              </div>
            ))}
          </div>
        </div>
      )}

      <div className="quick-links">
        <h2>クイックアクセス</h2>
        <div className="link-grid">
          <Link to="/fields" className="link-card">
            <span className="icon">🗺️</span>
            <span className="label">ほ場一覧</span>
          </Link>
          <Link to="/rotation" className="link-card">
            <span className="icon">🔄</span>
            <span className="label">輪作計画</span>
          </Link>
          <Link to="/plans" className="link-card">
            <span className="icon">📋</span>
            <span className="label">保存済み計画</span>
          </Link>
          <Link to="/pesticide-orders" className="link-card">
            <span className="icon">💊</span>
            <span className="label">農薬発注</span>
          </Link>
          <Link to="/pesticide-records" className="link-card">
            <span className="icon">🧪</span>
            <span className="label">防除記録</span>
          </Link>
        </div>
      </div>

      {isLoading && <Spinner text="統計情報を読み込み中..." />}
    </div>
  );
}
