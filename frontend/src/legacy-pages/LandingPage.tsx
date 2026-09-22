import React from 'react';
import { ArrowRight, BadgeCheck, BellRing, Database } from 'lucide-react';
import { Link } from 'react-router-dom';
import '../assets/landing.css';

/* Keep this export stable: the logo is shared by other product surfaces. */
export const DataTrustLogo: React.FC<{ size?: number; className?: string }> = ({ size = 24, className = '' }) => {
  const path = 'M 1.5,23 L 1.5,33 C 1.5,38.5 6,43 11.5,43 L 16.5,43 C 22,43 26.5,38.5 26.5,33 Q 28,28 33,26.5 C 38.5,26.5 43,22 43,16.5 L 43,11.5 C 43,6 38.5,1.5 33,1.5 L 23,1.5 Q 12,12 1.5,23 Z';

  return (
    <svg
      aria-hidden="true"
      className={className}
      fill="currentColor"
      height={size}
      viewBox="-50 -50 100 100"
      width={size}
      xmlns="http://www.w3.org/2000/svg"
    >
      <path d={path} transform="rotate(0)" />
      <path d={path} transform="rotate(90)" />
      <path d={path} transform="rotate(180)" />
      <path d={path} transform="rotate(270)" />
    </svg>
  );
};

const steps = [
  {
    icon: Database,
    title: 'Nạp dữ liệu',
    description: 'Chọn nguồn dữ liệu và đưa dữ liệu vào hệ thống để bắt đầu kiểm tra.',
  },
  {
    icon: BellRing,
    title: 'Kiểm tra cảnh báo',
    description: 'Xem các vấn đề được phát hiện, mức độ ảnh hưởng và bằng chứng liên quan.',
  },
  {
    icon: BadgeCheck,
    title: 'Duyệt đề xuất',
    description: 'Xác nhận hoặc từ chối đề xuất trước khi áp dụng thay đổi cho dữ liệu.',
  },
];

export const LandingPage: React.FC = () => (
  <div className="landing-page">
    <header className="landing-header">
      <Link className="landing-brand" to="/" aria-label="DataTrust OS — Trang chủ">
        <span className="landing-brand__mark"><DataTrustLogo size={20} /></span>
        <span>DataTrust OS</span>
      </Link>
      <a className="landing-header__help" href="#quy-trinh">Cách sử dụng</a>
    </header>

    <main>
      <section className="landing-hero" aria-labelledby="landing-title">
        <div className="landing-hero__copy">
          <p className="landing-eyebrow">Quản lý chất lượng dữ liệu</p>
          <h1 id="landing-title">Bắt đầu với dữ liệu của bạn</h1>
          <p className="landing-hero__lead">
            Nạp dữ liệu, xem cảnh báo và duyệt đề xuất sửa lỗi trong một quy trình rõ ràng.
            Bạn luôn là người quyết định trước khi hệ thống thay đổi dữ liệu.
          </p>

          <div className="landing-actions" aria-label="Bắt đầu sử dụng">
            <Link className="landing-button landing-button--primary" to="/dashboard/ingestion">
              Bắt đầu nạp dữ liệu
              <ArrowRight aria-hidden="true" size={18} />
            </Link>
            <Link className="landing-button landing-button--secondary" to="/workspace">
              Mở không gian phân tích
            </Link>
          </div>
          <p className="landing-hero__hint">Lần đầu sử dụng? Hãy bắt đầu bằng nút nạp dữ liệu.</p>
        </div>

        <aside className="landing-start-card" aria-labelledby="start-card-title">
          <div className="landing-start-card__icon"><Database aria-hidden="true" size={24} /></div>
          <p className="landing-start-card__label">Việc đầu tiên</p>
          <h2 id="start-card-title">Kết nối nguồn dữ liệu</h2>
          <p>Hệ thống cần dữ liệu đầu vào trước khi có thể phát hiện vấn đề và đưa ra đề xuất.</p>
          <Link className="landing-start-card__link" to="/dashboard/ingestion">
            Đi đến trang nạp dữ liệu <ArrowRight aria-hidden="true" size={16} />
          </Link>
        </aside>
      </section>

      <section className="landing-process" id="quy-trinh" aria-labelledby="process-title">
        <div className="landing-process__heading">
          <p className="landing-eyebrow">Quy trình đơn giản</p>
          <h2 id="process-title">Bạn chỉ cần làm 3 bước</h2>
          <p>Đi theo thứ tự từ trái sang phải. Mỗi bước đều cho biết rõ việc cần làm tiếp theo.</p>
        </div>

        <ol className="landing-steps">
          {steps.map(({ icon: Icon, title, description }, index) => (
            <li className="landing-step" key={title}>
              <div className="landing-step__top">
                <span className="landing-step__number">{index + 1}</span>
                <Icon aria-hidden="true" size={22} />
              </div>
              <h3>{title}</h3>
              <p>{description}</p>
            </li>
          ))}
        </ol>
      </section>
    </main>

    <footer className="landing-footer">
      <span>DataTrust OS</span>
      <span>Kiểm soát dữ liệu rõ ràng, có người phê duyệt.</span>
    </footer>
  </div>
);
