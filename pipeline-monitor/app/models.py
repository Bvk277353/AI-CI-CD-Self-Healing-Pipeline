"""
Database Models and Operations
SQLAlchemy models and database utilities
"""

from sqlalchemy import create_engine, Column, Integer, String, DateTime, Boolean, Text, Float, ARRAY, JSON
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from sqlalchemy.sql import func
from datetime import datetime, timedelta
from typing import List, Dict, Optional
import os
import logging

logger = logging.getLogger(__name__)

Base = declarative_base()

# Models
class PipelineRun(Base):
    __tablename__ = 'pipeline_runs'
    
    id = Column(Integer, primary_key=True)
    run_id = Column(String(255), unique=True, nullable=False, index=True)
    repo = Column(String(255), nullable=False)
    status = Column(String(50), nullable=False)
    conclusion = Column(String(50))
    started_at = Column(DateTime, nullable=False)
    completed_at = Column(DateTime)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    def to_dict(self):
        return {
            'id': self.id,
            'run_id': self.run_id,
            'repo': self.repo,
            'status': self.status,
            'conclusion': self.conclusion,
            'started_at': self.started_at.isoformat() if self.started_at else None,
            'completed_at': self.completed_at.isoformat() if self.completed_at else None,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }


class FailureLog(Base):
    __tablename__ = 'failure_logs'
    
    id = Column(Integer, primary_key=True)
    run_id = Column(String(255), nullable=False, index=True)
    error_type = Column(String(100), nullable=False, index=True)
    error_message = Column(Text)
    stack_trace = Column(Text)
    severity = Column(String(20))
    created_at = Column(DateTime, default=datetime.utcnow)
    
    def to_dict(self):
        return {
            'id': self.id,
            'run_id': self.run_id,
            'error_type': self.error_type,
            'error_message': self.error_message,
            'stack_trace': self.stack_trace,
            'severity': self.severity,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }


class HealingAction(Base):
    __tablename__ = 'healing_actions'
    
    id = Column(Integer, primary_key=True)
    run_id = Column(String(255), nullable=False, index=True)
    action_type = Column(String(100), nullable=False)
    success = Column(Boolean, nullable=False, index=True)
    details = Column(JSON)
    changes_made = Column(ARRAY(Text))
    created_at = Column(DateTime, default=datetime.utcnow)
    
    def to_dict(self):
        return {
            'id': self.id,
            'run_id': self.run_id,
            'action_type': self.action_type,
            'success': self.success,
            'details': self.details,
            'changes_made': self.changes_made,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }


class Metric(Base):
    __tablename__ = 'metrics'
    
    id = Column(Integer, primary_key=True)
    run_id = Column(String(255))
    metric_name = Column(String(100), nullable=False, index=True)
    metric_value = Column(Float, nullable=False)
    timestamp = Column(DateTime, default=datetime.utcnow, index=True)
    
    def to_dict(self):
        return {
            'id': self.id,
            'run_id': self.run_id,
            'metric_name': self.metric_name,
            'metric_value': self.metric_value,
            'timestamp': self.timestamp.isoformat() if self.timestamp else None
        }


# Database class
class Database:
    def __init__(self):
        self.database_url = os.getenv(
            'DATABASE_URL',
            'sqlite:///./local.db'
        )
        self.engine = None
        self.SessionLocal = None
    
    async def connect(self):
        """Initialize database connection"""
        try:
            if self.database_url.startswith("postgres"):
                self.engine = create_engine(
                    self.database_url,
                    pool_pre_ping=True,
                    connect_args={"sslmode": "require"}
                )

            else:
                # SQLite fallback (local only)
                self.engine = create_engine(
                    self.database_url,
                    connect_args={"check_same_thread": False}
                )

            self.SessionLocal = sessionmaker(
                autocommit=False,
                autoflush=False,
                bind=self.engine
            )

            # Create tables if they don't exist
            Base.metadata.create_all(bind=self.engine)

            logger.info("✅ Database connected successfully")

        except Exception as e:
            logger.error(f"Database connection failed: {e}")
            raise
    
    async def disconnect(self):
        """Close database connection"""
        if self.engine:
            self.engine.dispose()
            logger.info("Database connection closed")
    
    async def is_connected(self) -> bool:
        """Check if database is connected"""
        try:
            if self.engine:
                with self.engine.connect() as conn:
                    conn.execute("SELECT 1")
                return True
        except:
            pass
        return False
    
    def get_session(self):
        """Get database session"""
        if not self.SessionLocal:
            raise Exception("Database not connected")
        return self.SessionLocal()
    
    # Pipeline Run operations
    async def create_pipeline_run(
        self,
        run_id: str,
        repo: str,
        status: str,
        conclusion: Optional[str],
        started_at: datetime,
        completed_at: Optional[datetime]
    ) -> PipelineRun:
        """Create a new pipeline run record"""
        session = self.get_session()
        try:
            # Check if already exists
            existing = session.query(PipelineRun).filter_by(run_id=run_id).first()
            if existing:
                # Update existing
                existing.status = status
                existing.conclusion = conclusion
                existing.completed_at = completed_at
                session.commit()
                return existing
            
            # Create new
            pipeline_run = PipelineRun(
                run_id=run_id,
                repo=repo,
                status=status,
                conclusion=conclusion,
                started_at=started_at,
                completed_at=completed_at
            )
            session.add(pipeline_run)
            session.commit()
            session.refresh(pipeline_run)
            return pipeline_run
        finally:
            session.close()
    
    async def get_pipeline_run(self, run_id: str) -> Optional[PipelineRun]:
        """Get pipeline run by ID"""
        session = self.get_session()
        try:
            return session.query(PipelineRun).filter_by(run_id=run_id).first()
        finally:
            session.close()
    
    async def get_recent_runs(self, limit: int = 10) -> List[Dict]:
        """Get recent pipeline runs"""
        session = self.get_session()
        try:
            runs = session.query(PipelineRun)\
                .order_by(PipelineRun.created_at.desc())\
                .limit(limit)\
                .all()
            
            result = []
            for run in runs:
                # Get healing info
                healing = session.query(HealingAction)\
                    .filter_by(run_id=run.run_id)\
                    .first()
                
                result.append({
                    **run.to_dict(),
                    'failure_predicted': False,  # Would come from prediction service
                    'healing_attempted': healing is not None,
                    'healing_successful': healing.success if healing else False
                })
            
            return result
        finally:
            session.close()
    
    # Failure Log operations
    async def create_failure_log(
        self,
        run_id: str,
        error_type: str,
        error_message: str,
        stack_trace: str,
        severity: str = "medium"
    ) -> FailureLog:
        """Create a failure log entry"""
        session = self.get_session()
        try:
            failure_log = FailureLog(
                run_id=run_id,
                error_type=error_type,
                error_message=error_message,
                stack_trace=stack_trace,
                severity=severity
            )
            session.add(failure_log)
            session.commit()
            session.refresh(failure_log)
            return failure_log
        finally:
            session.close()
    
    async def get_failure_patterns(self) -> List[Dict]:
        """Get common failure patterns with frequencies"""
        session = self.get_session()
        try:
            # Query failure patterns from last 30 days
            thirty_days_ago = datetime.utcnow() - timedelta(days=30)
            
            results = session.query(
                FailureLog.error_type,
                func.count(FailureLog.id).label('count'),
                func.avg(
                    session.query(HealingAction.success)
                    .filter(HealingAction.run_id == FailureLog.run_id)
                    .correlate(FailureLog)
                    .scalar_subquery()
                ).label('healing_success_rate')
            ).filter(
                FailureLog.created_at >= thirty_days_ago
            ).group_by(
                FailureLog.error_type
            ).order_by(
                func.count(FailureLog.id).desc()
            ).all()
            
            return [
                {
                    'error_type': result.error_type,
                    'count': result.count,
                    'healing_success_rate': float(result.healing_success_rate or 0) * 100
                }
                for result in results
            ]
        finally:
            session.close()
    
    # Healing Action operations
    async def create_healing_action(
        self,
        run_id: str,
        action_type: str,
        success: bool,
        details: Dict,
        changes_made: List[str] = None
    ) -> HealingAction:
        """Create a healing action record"""
        session = self.get_session()
        try:
            healing_action = HealingAction(
                run_id=run_id,
                action_type=action_type,
                success=success,
                details=details,
                changes_made=changes_made or []
            )
            session.add(healing_action)
            session.commit()
            session.refresh(healing_action)
            return healing_action
        finally:
            session.close()
    
    async def get_healing_history(self, run_id: str) -> Optional[Dict]:
        """Get healing history for a pipeline run"""
        session = self.get_session()
        try:
            run = session.query(PipelineRun).filter_by(run_id=run_id).first()
            if not run:
                return None
            
            failures = session.query(FailureLog)\
                .filter_by(run_id=run_id)\
                .all()
            
            healings = session.query(HealingAction)\
                .filter_by(run_id=run_id)\
                .all()
            
            return {
                'pipeline_run': run.to_dict(),
                'failures': [f.to_dict() for f in failures],
                'healing_actions': [h.to_dict() for h in healings]
            }
        finally:
            session.close()
    
    # Statistics operations
    async def get_healing_statistics(self) -> Dict:
        """Get overall healing statistics"""
        session = self.get_session()
        try:
            thirty_days_ago = datetime.utcnow() - timedelta(days=30)
            
            # Total failures
            total_failures = session.query(func.count(PipelineRun.id))\
                .filter(
                    PipelineRun.conclusion == 'failure',
                    PipelineRun.created_at >= thirty_days_ago
                ).scalar()
            
            # Healing attempts
            healing_attempted = session.query(func.count(HealingAction.id))\
                .filter(HealingAction.created_at >= thirty_days_ago)\
                .scalar()
            
            # Successful healings
            healing_successful = session.query(func.count(HealingAction.id))\
                .filter(
                    HealingAction.success == True,
                    HealingAction.created_at >= thirty_days_ago
                ).scalar()
            
            # Success rate
            success_rate = (healing_successful / healing_attempted * 100) \
                if healing_attempted > 0 else 0
            
            # Time saved (assuming 15 min per manual fix)
            time_saved = healing_successful * 15
            
            # Cost saved (assuming $1.50 per prevented re-run)
            cost_saved = healing_successful * 1.50
            
            return {
                'total_failures': total_failures,
                'healing_attempted': healing_attempted,
                'healing_successful': healing_successful,
                'success_rate': round(success_rate, 2),
                'time_saved': time_saved,
                'cost_saved': round(cost_saved, 2)
            }
        finally:
            session.close()
    
    # Metrics operations
    async def record_metric(
        self,
        metric_name: str,
        metric_value: float,
        run_id: Optional[str] = None
    ):
        """Record a metric"""
        session = self.get_session()
        try:
            metric = Metric(
                run_id=run_id,
                metric_name=metric_name,
                metric_value=metric_value
            )
            session.add(metric)
            session.commit()
        finally:
            session.close()
    
    async def get_metrics(
        self,
        metric_name: str,
        hours: int = 24
    ) -> List[Dict]:
        """Get metrics for a specific period"""
        session = self.get_session()
        try:
            start_time = datetime.utcnow() - timedelta(hours=hours)
            
            metrics = session.query(Metric)\
                .filter(
                    Metric.metric_name == metric_name,
                    Metric.timestamp >= start_time
                )\
                .order_by(Metric.timestamp.asc())\
                .all()
            
            return [m.to_dict() for m in metrics]
        finally:
            session.close()
    
    async def cleanup_old_data(self, days: int = 90):
        """Clean up data older than specified days"""
        session = self.get_session()
        try:
            cutoff_date = datetime.utcnow() - timedelta(days=days)
            
            # Delete old metrics
            session.query(Metric)\
                .filter(Metric.timestamp < cutoff_date)\
                .delete()
            
            # Delete old failure logs
            old_runs = session.query(PipelineRun.run_id)\
                .filter(PipelineRun.created_at < cutoff_date)\
                .all()
            
            run_ids = [run.run_id for run in old_runs]
            
            if run_ids:
                session.query(FailureLog)\
                    .filter(FailureLog.run_id.in_(run_ids))\
                    .delete(synchronize_session=False)
                
                session.query(HealingAction)\
                    .filter(HealingAction.run_id.in_(run_ids))\
                    .delete(synchronize_session=False)
                
                session.query(PipelineRun)\
                    .filter(PipelineRun.run_id.in_(run_ids))\
                    .delete(synchronize_session=False)
            
            session.commit()
            logger.info(f"Cleaned up data older than {days} days")
        finally:
            session.close()
