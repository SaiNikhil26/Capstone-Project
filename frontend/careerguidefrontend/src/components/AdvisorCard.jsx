import { Lightbulb, BookOpen, Quote } from 'lucide-react';
import './AdvisorCard.css';

export default function AdvisorCard({ recommendation, skillGap }) {
  if (!recommendation) return null;

  return (
    <div className="glass-panel advisor-card">
      <div className="advisor-header">
        <div className="advisor-icon-wrapper">
          <Lightbulb size={24} className="text-gradient" />
        </div>
        <h2>Learning Advisor</h2>
      </div>

      <div className="advisor-content">
        <div className="advisor-summary">
          <Quote size={20} className="quote-mark" />
          <p>{recommendation.summary}</p>
        </div>

        <div className="split-grid">
          {/* Actionable Tips */}
          <div className="tips-section">
            <h3><BookOpen size={18} /> Study Tips</h3>
            <ul className="tips-list">
              {recommendation.tips.map((tip, i) => (
                <li key={i}>{tip}</li>
              ))}
            </ul>
          </div>

          {/* Skill gaps */}
          {skillGap?.has_gaps && (
            <div className="gaps-section">
              <h3>Missing Prerequisites</h3>
              <div className="tags-container">
                {skillGap.missing_skills.map((skill, i) => (
                  <span key={i} className="gap-tag">{skill}</span>
                ))}
              </div>
              
              {skillGap.foundational_topics?.length > 0 && (
                <div className="foundational-topics">
                  <h4>Recommended to search first:</h4>
                  <div className="tags-container">
                    {skillGap.foundational_topics.map((topic, i) => (
                      <span key={i} className="topic-tag">{topic}</span>
                    ))}
                  </div>
                </div>
              )}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
