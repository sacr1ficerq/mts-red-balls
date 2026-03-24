"""
Tests for Kaggle tools
"""

import pytest
import os
import json
from unittest.mock import Mock, patch, MagicMock
import pandas as pd

from kaggle_solver.tools.kaggle import (
    kaggle_get_competition_info,
    kaggle_download_data,
    kaggle_submit,
    kaggle_get_submission_status,
    kaggle_get_leaderboard,
    kaggle_list_competitions,
    kaggle_validate_submission,
    kaggle_prepare_submission
)


class TestKaggleTools:
    """Test suite for Kaggle tools"""
    
    @pytest.fixture
    def mock_kaggle_client(self):
        """Mock Kaggle MCP client"""
        with patch('kaggle_solver.tools.kaggle.get_kaggle_mcp_client') as mock_get_client:
            mock_client = Mock()
            mock_get_client.return_value = mock_client
            yield mock_client
    
    @pytest.fixture
    def sample_competition_info(self):
        """Sample competition information"""
        return {
            'name': 'titanic',
            'title': 'Titanic - Machine Learning from Disaster',
            'description': 'Predict which passengers survived',
            'evaluation_metric': 'accuracy',
            'max_daily_submissions': 5,
            'max_team_size': 3,
            'reward': 'None',
            'deadline': '2024-12-31',
            'total_teams': 15000,
            'total_submissions': 50000
        }
    
    @pytest.fixture
    def sample_submission_df(self):
        """Sample submission DataFrame"""
        return pd.DataFrame({
            'PassengerId': [892, 893, 894],
            'Survived': [0, 1, 0]
        })
    
    @pytest.fixture
    def sample_predictions_df(self):
        """Sample predictions DataFrame"""
        return pd.DataFrame({
            'PassengerId': [892, 893, 894],
            'Survived': [0.2, 0.8, 0.3]
        })
    
    def test_kaggle_get_competition_info_success(self, mock_kaggle_client, sample_competition_info):
        """Test successful competition info retrieval"""
        mock_kaggle_client.get_competition_info.return_value = sample_competition_info
        
        result = kaggle_get_competition_info(query='titanic')
        
        assert result['success'] is True
        assert result['data'] == sample_competition_info
        mock_kaggle_client.get_competition_info.assert_called_once_with('titanic')
    
    def test_kaggle_get_competition_info_no_client(self):
        """Test competition info retrieval when client is not available"""
        with patch('kaggle_solver.tools.kaggle.get_kaggle_mcp_client') as mock_get_client:
            mock_get_client.return_value = None
            
            result = kaggle_get_competition_info(query='titanic')
            
            assert result['success'] is False
            assert 'Kaggle API credentials are not configured' in result['error']
    
    def test_kaggle_get_competition_info_error(self, mock_kaggle_client):
        """Test competition info retrieval with error"""
        mock_kaggle_client.get_competition_info.side_effect = Exception('API Error')
        
        result = kaggle_get_competition_info(query='titanic')
        
        assert result['success'] is False
        assert 'API Error' in result['error']
    
    def test_kaggle_download_data_success(self, mock_kaggle_client):
        """Test successful data download"""
        mock_kaggle_client.download_competition_data.return_value = [
            './data/train.csv',
            './data/test.csv',
            './data/sample_submission.csv'
        ]
        
        result = kaggle_download_data(query='titanic', path='./data')
        
        assert result['success'] is True
        assert result['data']['competition'] == 'titanic'
        assert len(result['data']['downloaded_files']) == 3
        args, _ = mock_kaggle_client.download_competition_data.call_args
        assert args[0] == 'titanic'
        assert args[1].endswith('data')
    
    def test_kaggle_download_data_specific_files(self, mock_kaggle_client):
        """Test downloading specific files"""
        mock_kaggle_client.download_competition_data.return_value = [
            './data/train.csv',
            './data/test.csv'
        ]
        
        result = kaggle_download_data(
            query='titanic',
            path='./data',
            files='train.csv,test.csv'
        )
        
        assert result['success'] is True
        assert len(result['data']['downloaded_files']) == 2
        args, _ = mock_kaggle_client.download_competition_data.call_args
        assert args[0] == 'titanic'
        assert args[1].endswith('data')
        assert args[2] == ['train.csv', 'test.csv']
    
    def test_kaggle_submit_success(self, mock_kaggle_client):
        """Test successful submission"""
        mock_kaggle_client.submit_prediction.return_value = {
            'status': 'complete',
            'message': 'Test submission',
            'submitted_at': '2024-01-15 14:30:00',
            'submission_id': '12345678'
        }
        
        result = kaggle_submit(
            query='titanic',
            submission_file='submission.csv',
            message='Test submission'
        )
        
        assert result['success'] is True
        assert result['data']['submission_id'] == '12345678'
        args, _ = mock_kaggle_client.submit_prediction.call_args
        assert args[0] == 'titanic'
        assert args[1].endswith('submission.csv')
        assert args[2] == 'Test submission'
    
    def test_kaggle_get_submission_status_success(self, mock_kaggle_client):
        """Test successful submission status retrieval"""
        mock_kaggle_client.get_submission_status.return_value = {
            'status': 'complete',
            'public_score': 0.78947,
            'private_score': None,
            'submitted_at': '2024-01-15 14:30:00',
            'message': 'Test submission'
        }
        
        result = kaggle_get_submission_status(
            query='titanic',
            submission_id='12345678'
        )
        
        assert result['success'] is True
        assert result['data']['public_score'] == 0.78947
        mock_kaggle_client.get_submission_status.assert_called_once_with('titanic', '12345678')
    
    def test_kaggle_get_leaderboard_success(self, mock_kaggle_client):
        """Test successful leaderboard retrieval"""
        mock_kaggle_client.get_leaderboard.return_value = [
            {
                'team_name': 'Team Alpha',
                'team_id': '12345',
                'rank': 1,
                'score': 0.85,
                'last_submission': '2024-01-15 14:30:00'
            },
            {
                'team_name': 'Team Beta',
                'team_id': '67890',
                'rank': 2,
                'score': 0.84,
                'last_submission': '2024-01-15 13:45:00'
            }
        ]
        
        result = kaggle_get_leaderboard(query='titanic')
        
        assert result['success'] is True
        assert len(result['data']) == 2
        assert result['data'][0]['rank'] == 1
        mock_kaggle_client.get_leaderboard.assert_called_once_with('titanic')
    
    def test_kaggle_list_competitions_success(self, mock_kaggle_client):
        """Test successful competition listing"""
        mock_kaggle_client.list_competitions.return_value = [
            {
                'name': 'titanic',
                'title': 'Titanic - Machine Learning from Disaster',
                'category': 'gettingStarted',
                'reward': 'None',
                'deadline': '2024-12-31',
                'total_teams': 15000
            }
        ]
        
        result = kaggle_list_competitions(category='gettingStarted')
        
        assert result['success'] is True
        assert len(result['data']) == 1
        assert result['data'][0]['name'] == 'titanic'
        mock_kaggle_client.list_competitions.assert_called_once_with(category='gettingStarted', search='')
    
    def test_kaggle_validate_submission_valid(self, sample_submission_df, tmp_path):
        """Test validation of valid submission"""
        # Create sample files
        sample_file = tmp_path / 'sample_submission.csv'
        submission_file = tmp_path / 'submission.csv'
        
        sample_submission_df.to_csv(sample_file, index=False)
        sample_submission_df.to_csv(submission_file, index=False)
        
        result = kaggle_validate_submission(
            query='titanic',
            submission_file=str(submission_file),
            sample_file=str(sample_file)
        )
        
        assert result['success'] is True
        assert result['data']['valid'] is True
        assert len(result['data']['issues']) == 0
    
    def test_kaggle_validate_submission_invalid_columns(self, sample_submission_df, tmp_path):
        """Test validation with invalid columns"""
        sample_file = tmp_path / 'sample_submission.csv'
        submission_file = tmp_path / 'submission.csv'
        
        sample_submission_df.to_csv(sample_file, index=False)
        
        # Create submission with wrong columns
        invalid_df = pd.DataFrame({
            'ID': [892, 893, 894],
            'Target': [0, 1, 0]
        })
        invalid_df.to_csv(submission_file, index=False)
        
        result = kaggle_validate_submission(
            query='titanic',
            submission_file=str(submission_file),
            sample_file=str(sample_file)
        )
        
        # The validation operation itself succeeded, but found issues
        assert result['success'] is True
        assert result['data']['valid'] is False
        assert len(result['data']['issues']) > 0
        # Check that issues contain column mismatch
        issues_text = ' '.join(result['data']['issues'])
        assert 'Column' in issues_text or 'column' in issues_text
    
    def test_kaggle_validate_submission_missing_values(self, sample_submission_df, tmp_path):
        """Test validation with missing values"""
        sample_file = tmp_path / 'sample_submission.csv'
        submission_file = tmp_path / 'submission.csv'
        
        sample_submission_df.to_csv(sample_file, index=False)
        
        # Create submission with missing values
        invalid_df = sample_submission_df.copy()
        invalid_df.loc[0, 'Survived'] = None
        invalid_df.to_csv(submission_file, index=False)
        
        result = kaggle_validate_submission(
            query='titanic',
            submission_file=str(submission_file),
            sample_file=str(sample_file)
        )
        
        assert result['success'] is True
        assert result['data']['valid'] is False
        assert any('Missing values' in issue for issue in result['data']['issues'])
    
    def test_kaggle_prepare_submission_success(self, sample_submission_df, sample_predictions_df, tmp_path):
        """Test successful submission preparation"""
        sample_file = tmp_path / 'sample_submission.csv'
        predictions_file = tmp_path / 'predictions.csv'
        output_file = tmp_path / 'submission.csv'
        
        sample_submission_df.to_csv(sample_file, index=False)
        sample_predictions_df.to_csv(predictions_file, index=False)
        
        result = kaggle_prepare_submission(
            query='titanic',
            predictions_file=str(predictions_file),
            sample_file=str(sample_file),
            output_file=str(output_file)
        )
        
        assert result['success'] is True
        assert result['data']['rows'] == 3
        assert result['data']['columns'] == ['PassengerId', 'Survived']
        assert output_file.exists()
        
        # Verify output file
        output_df = pd.read_csv(output_file)
        assert len(output_df) == 3
        assert list(output_df.columns) == ['PassengerId', 'Survived']
    
    def test_kaggle_prepare_submission_sorts_by_id(self, sample_submission_df, tmp_path):
        """Test that submission preparation sorts by ID"""
        sample_file = tmp_path / 'sample_submission.csv'
        predictions_file = tmp_path / 'predictions.csv'
        output_file = tmp_path / 'submission.csv'
        
        sample_submission_df.to_csv(sample_file, index=False)
        
        # Create predictions with unsorted IDs
        unsorted_df = pd.DataFrame({
            'PassengerId': [894, 892, 893],
            'Survived': [0.3, 0.2, 0.8]
        })
        unsorted_df.to_csv(predictions_file, index=False)
        
        result = kaggle_prepare_submission(
            query='titanic',
            predictions_file=str(predictions_file),
            sample_file=str(sample_file),
            output_file=str(output_file)
        )
        
        assert result['success'] is True
        
        # Verify output is sorted
        output_df = pd.read_csv(output_file)
        assert list(output_df['PassengerId']) == [892, 893, 894]


class TestKaggleToolsIntegration:
    """Integration tests for Kaggle tools"""
    
    def test_full_workflow_simulation(self, tmp_path):
        """Test simulation of full Kaggle workflow"""
        # Create sample files
        sample_df = pd.DataFrame({
            'PassengerId': [892, 893, 894],
            'Survived': [0, 1, 0]
        })
        
        sample_file = tmp_path / 'sample_submission.csv'
        predictions_file = tmp_path / 'predictions.csv'
        submission_file = tmp_path / 'submission.csv'
        
        sample_df.to_csv(sample_file, index=False)
        sample_df.to_csv(predictions_file, index=False)
        
        # Prepare submission
        result = kaggle_prepare_submission(
            query='titanic',
            predictions_file=str(predictions_file),
            sample_file=str(sample_file),
            output_file=str(submission_file)
        )
        
        assert result['success'] is True
        
        # Validate submission
        result = kaggle_validate_submission(
            query='titanic',
            submission_file=str(submission_file),
            sample_file=str(sample_file)
        )
        
        assert result['success'] is True
        assert result['data']['valid'] is True


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
